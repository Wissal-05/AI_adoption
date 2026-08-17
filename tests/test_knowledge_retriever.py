import os
import shutil
import pytest
from adoption_analytics.ai.knowledge_retriever import KnowledgeRetriever

@pytest.fixture(scope="module")
def retriever():
    # S'assurer qu'on reconstruit l'index à partir de zéro pour le test
    index_path = os.path.join("data", "rag", "index.json")
    if os.path.exists(index_path):
        os.remove(index_path)
        
    r = KnowledgeRetriever(docs_dir="docs/knowledge")
    r.build_index()
    return r

def test_corpus_loaded_and_indexed(retriever):
    assert len(retriever.documents) > 0, "Le corpus doit contenir des chunks"
    
def test_search_mau(retriever):
    results = retriever.search("Que signifie MAU ?", top_k=2)
    assert len(results) > 0
    # On s'attend à trouver kpi_definitions.md
    sources = [r["source"] for r in results]
    assert "kpi_definitions.md" in sources

def test_search_transport(retriever):
    results = retriever.search("Pourquoi Transport n'a pas de taux d'adoption ?", top_k=2)
    assert len(results) > 0
    # Doit retrouver data_limitations.md (ou services.md, mais limitation Booking est pertinent)
    found_limitation = any(
        r["source"] == "data_limitations.md" and "Booking" in r["section"]
        for r in results
    )
    assert found_limitation, f"On s'attendait à data_limitations.md section Limitations Booking. Obtenu: {results}"

def test_search_source_ip(retriever):
    results = retriever.search("Une adresse IP correspond-elle forcément à un utilisateur du Learning Center ?", top_k=2)
    assert len(results) > 0
    sources = [r["source"] for r in results]
    assert "data_limitations.md" in sources
    found_lc = any("Learning Center" in r["section"] for r in results)
    assert found_lc

def test_results_metadata(retriever):
    results = retriever.search("DAU", top_k=1)
    assert len(results) > 0
    res = results[0]
    assert "source" in res
    assert "section" in res
    assert "chunk_id" in res
    assert "score" in res
    assert "content" in res

def test_rebuild_is_idempotent(retriever):
    initial_count = len(retriever.documents)
    # Reconstruire sans détruire le directory JSON
    retriever.build_index()
    assert len(retriever.documents) == initial_count, "La reconstruction doit être idempotente et ne pas dupliquer"
