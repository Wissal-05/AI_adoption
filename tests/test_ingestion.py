"""Suite de tests unitaires et d'intégration pour le pipeline d'ingestion.

Couvre la première ingestion, l'ingestion incrémentale, l'idempotence, la déduplication,
la gestion des checkpoints en cas d'erreur, la mise à jour des KPI quotidiens,
le traitement des cas limites (DF vide, timestamp invalide) et les sources inconnues.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import pandas as pd
import pytest

from adoption_analytics.ingestion.checkpoint import JSONCheckpointRepository, IngestionCheckpoint
from adoption_analytics.ingestion.deduplication import generate_event_id, deduplicate_events
from adoption_analytics.ingestion.pipeline import LearningCenterIngestionPipeline
from adoption_analytics.storage.file_repository import FileStorageRepository


# ── FIXTURES DE TEST DE DONNÉES ────────────────────────────────────────────────

@pytest.fixture
def sample_nginx_log_row() -> dict:
    return {
        "event_time_local": "2026-07-21T10:00:00+01:00",
        "visitor_id_approx": "u_test_123",
        "client_ip": "10.0.0.1",
        "path": "/wp-admin",
        "status": 404,
        "user_agent": "Mozilla",
        "analytics_eligible": 1,
        "is_bot": 0,
        "is_static": 0,
        "is_api": 0,
        "event_type": "page_view",
    }


# ── TESTS UNITAIRES DE DÉDUPLICATION ───────────────────────────────────────────

class TestDeduplication:
    def test_generate_event_id_is_deterministic(self, sample_nginx_log_row):
        id1 = generate_event_id(sample_nginx_log_row)
        id2 = generate_event_id(sample_nginx_log_row)
        assert id1 == id2
        assert len(id1) == 64  # SHA-256 hex string length

    def test_generate_event_id_differs_on_field_change(self, sample_nginx_log_row):
        id1 = generate_event_id(sample_nginx_log_row)
        row_diff = sample_nginx_log_row.copy()
        row_diff["status"] = 200
        id2 = generate_event_id(row_diff)
        assert id1 != id2

    def test_deduplicate_events_filters_duplicates(self):
        df = pd.DataFrame([
            {"event_id": "id_1", "visitor_id_approx": "u1", "event_timestamp": pd.Timestamp("2026-07-20")},
            {"event_id": "id_1", "visitor_id_approx": "u1", "event_timestamp": pd.Timestamp("2026-07-20")},
            {"event_id": "id_2", "visitor_id_approx": "u2", "event_timestamp": pd.Timestamp("2026-07-20")},
        ])
        existing = {"id_2"}

        dedup_df, ignored = deduplicate_events(df, existing)

        # Doit rester uniquement id_2 (qui est exclu par existing) et id_1 (dont un doublon est ignoré)
        # Mais id_2 est dans existing, donc il est retiré.
        # Donc seul un unique id_1 reste.
        assert len(dedup_df) == 1
        assert dedup_df.iloc[0]["event_id"] == "id_1"
        assert ignored == 2  # 1 doublon interne + 1 doublon externe


# ── TESTS DU REPOSITORY ET PIPELINE D'INGESTION ────────────────────────────────

class TestIngestionPipeline:
    def test_first_ingestion_creates_files(self, tmp_path, sample_nginx_log_row):
        # Configuration avec des dépôts temporaires pour l'isolation
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")

        # Fichier source temporaire avec une seule ligne
        source_file = tmp_path / "nginx-events-test.csv"
        pd.DataFrame([sample_nginx_log_row]).to_csv(source_file, index=False)

        pipeline = LearningCenterIngestionPipeline(
            checkpoint_repo=checkpoint_repo,
            storage_repo=storage_repo,
            source_file_path=source_file
        )

        stats = pipeline.run()

        # Assertions exécution
        assert stats["status"] == "SUCCESS"
        assert stats["rows_read"] == 1
        assert stats["rows_added"] == 1
        assert stats["duplicates_ignored"] == 0

        # Assertions persistance
        assert (tmp_path / "processed" / "events_learning_center.csv").exists()
        assert (tmp_path / "processed" / "daily_kpis_learning_center.csv").exists()
        
        # Checkpoint créé
        chk = checkpoint_repo.load("learning_center")
        assert chk.status == "SUCCESS"
        assert chk.rows_added == 1
        assert chk.last_processed_timestamp is not None

    def test_incremental_ingestion_adds_only_new_rows(self, tmp_path, sample_nginx_log_row):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")

        # Ligne 1
        source_file = tmp_path / "nginx-events-test.csv"
        pd.DataFrame([sample_nginx_log_row]).to_csv(source_file, index=False)

        pipeline = LearningCenterIngestionPipeline(
            checkpoint_repo=checkpoint_repo,
            storage_repo=storage_repo,
            source_file_path=source_file
        )

        # Ingestion 1
        pipeline.run()
        chk1 = checkpoint_repo.load("learning_center")

        # Ingestion 2 avec de nouvelles lignes
        row2 = sample_nginx_log_row.copy()
        row2["event_time_local"] = "2026-07-21T11:00:00+01:00"
        row2["visitor_id_approx"] = "u_new"

        pd.DataFrame([sample_nginx_log_row, row2]).to_csv(source_file, index=False)

        pipeline2 = LearningCenterIngestionPipeline(
            checkpoint_repo=checkpoint_repo,
            storage_repo=storage_repo,
            source_file_path=source_file
        )
        stats2 = pipeline2.run()

        assert stats2["status"] == "SUCCESS"
        assert stats2["rows_read"] == 2  # Les deux lignes sont lues en raison du décalage horaire brut vs UTC
        assert stats2["rows_added"] == 1

    def test_ingestion_no_new_rows_is_idempotent(self, tmp_path, sample_nginx_log_row):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")
        source_file = tmp_path / "nginx-events-test.csv"
        pd.DataFrame([sample_nginx_log_row]).to_csv(source_file, index=False)

        # Run 1
        pipeline = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        pipeline.run()
        chk1 = checkpoint_repo.load("learning_center")

        # Run 2 sans changement dans le fichier
        pipeline2 = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        stats2 = pipeline2.run()

        assert stats2["status"] == "SUCCESS"
        assert stats2["rows_added"] == 0
        chk2 = checkpoint_repo.load("learning_center")
        assert chk2.last_processed_timestamp == chk1.last_processed_timestamp

    def test_checkpoint_not_updated_on_failure(self, tmp_path, sample_nginx_log_row):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")
        source_file = tmp_path / "nginx-events-test.csv"
        pd.DataFrame([sample_nginx_log_row]).to_csv(source_file, index=False)

        # Premier run réussi
        pipeline = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        pipeline.run()
        chk_good = checkpoint_repo.load("learning_center")

        # Écrit une NOUVELLE ligne pour forcer l'ingestion à passer par persist()
        row2 = sample_nginx_log_row.copy()
        row2["event_time_local"] = "2026-07-21T11:00:00+01:00"
        row2["visitor_id_approx"] = "u_fail_test"
        pd.DataFrame([sample_nginx_log_row, row2]).to_csv(source_file, index=False)

        # Deuxième run qui va lever une exception dans persist
        class FaultyPipeline(LearningCenterIngestionPipeline):
            def persist(self, df):
                raise IOError("Écriture disque impossible")

        faulty = FaultyPipeline(checkpoint_repo, storage_repo, source_file)
        
        with pytest.raises(IOError):
            faulty.run()

        chk_bad = checkpoint_repo.load("learning_center")
        # Le statut du checkpoint doit passer à FAILED, mais le timestamp d'ingestion
        # ne doit pas avoir bougé (conservant la valeur du premier run réussi).
        assert chk_bad.status == "FAILED"
        assert chk_bad.last_processed_timestamp == chk_good.last_processed_timestamp

    def test_kpi_current_day_is_provisional(self, tmp_path, sample_nginx_log_row):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")
        
        # Configure le log à la date d'aujourd'hui
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        row_today = sample_nginx_log_row.copy()
        row_today["event_time_local"] = f"{today_str}T10:00:00+01:00"

        source_file = tmp_path / "nginx-events-test.csv"
        pd.DataFrame([row_today]).to_csv(source_file, index=False)

        pipeline = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        pipeline.run()

        # Le KPI généré pour aujourd'hui doit avoir le statut provisional
        kpis_df = storage_repo.get_daily_kpis("learning_center")
        assert not kpis_df.empty
        today_kpi = kpis_df[kpis_df["date"] == pd.Timestamp(today_str)].iloc[0]
        assert today_kpi["status"] == "provisional"

    def test_empty_dataframe_does_not_fail(self, tmp_path):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")
        source_file = tmp_path / "nginx-events-test.csv"
        
        # Écrit un CSV vide (uniquement les colonnes)
        pd.DataFrame(columns=["event_time_local", "visitor_id_approx"]).to_csv(source_file, index=False)

        pipeline = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        stats = pipeline.run()

        assert stats["status"] == "SUCCESS"
        assert stats["rows_read"] == 0

    def test_invalid_timestamps_are_rejected(self, tmp_path, sample_nginx_log_row):
        checkpoint_repo = JSONCheckpointRepository(directory=tmp_path / "checkpoints")
        storage_repo = FileStorageRepository(data_dir=tmp_path / "processed")
        source_file = tmp_path / "nginx-events-test.csv"

        # Ligne avec date invalide
        row_bad = sample_nginx_log_row.copy()
        row_bad["event_time_local"] = "date-invalide"

        pd.DataFrame([row_bad]).to_csv(source_file, index=False)

        pipeline = LearningCenterIngestionPipeline(checkpoint_repo, storage_repo, source_file)
        
        # Le pipeline doit ignorer ou rejeter la ligne car le timestamp est invalide
        stats = pipeline.run()
        assert stats["status"] == "SUCCESS"
        assert stats["rows_added"] == 0

    def test_unknown_source_cli_fails(self):
        # Test du comportement en cas d'argument inconnu (CLI)
        with pytest.raises(SystemExit):
            import subprocess
            # Simule l'appel CLI avec une source invalide
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["pipeline.py", "--source", "unknown_source"]
                from adoption_analytics.ingestion.pipeline import main
                main()
            finally:
                sys.argv = old_argv
