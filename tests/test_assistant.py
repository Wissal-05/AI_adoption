"""Tests du moteur d'assistant IA."""

import pandas as pd
import pytest

from adoption_analytics.ai.keyword_engine import KeywordEngine
from adoption_analytics.ai.port import AssistantPort


class TestKeywordEngine:
    def setup_method(self):
        self.engine = KeywordEngine()

    def test_implements_assistant_port(self):
        assert isinstance(self.engine, AssistantPort)

    def test_detects_underused_intent(self, sample_usage_df):
        context = {"usage_df": sample_usage_df, "web_logs_df": pd.DataFrame()}
        response = self.engine.answer("Quels services sont les moins utilisés ?", context)
        assert "Services les moins utilisés" in response or "aucune donnée" in response

    def test_detects_department_intent(self, sample_usage_df):
        context = {"usage_df": sample_usage_df, "web_logs_df": pd.DataFrame()}
        response = self.engine.answer("Montre-moi l'usage par département", context)
        assert "département" in response.lower() or "aucune donnée" in response

    def test_detects_security_intent(self, sample_web_logs_df):
        context = {"usage_df": pd.DataFrame(), "web_logs_df": sample_web_logs_df}
        response = self.engine.answer("Y a-t-il des routes suspectes ?", context)
        assert "Routes suspectes" in response or "aucune donnée" in response

    def test_detects_inactive_intent(self, sample_usage_df):
        context = {"usage_df": sample_usage_df, "web_logs_df": pd.DataFrame()}
        response = self.engine.answer("Qui sont les utilisateurs inactifs ?", context)
        assert "inactifs" in response.lower() or "aucune donnée" in response

    def test_unknown_intent_returns_help(self):
        context = {"usage_df": pd.DataFrame(), "web_logs_df": pd.DataFrame()}
        response = self.engine.answer("Quelle est la météo ?", context)
        assert "Je peux répondre" in response

    def test_empty_context_does_not_raise(self):
        response = self.engine.answer("services sous-utilisés", context={})
        assert isinstance(response, str)

    def test_answers_mau_question(self, sample_usage_df):
        engine = KeywordEngine()

        response = engine.answer(
            "Quel est le MAU ?",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
            },
        )

        assert "MAU" in response
        assert "utilisateurs actifs" in response

    def test_answers_dau_question(self, sample_usage_df):
        engine = KeywordEngine()

        response = engine.answer(
            "Quel est le DAU ?",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
            },
        )

        assert "DAU" in response
        assert "utilisateurs actifs" in response

    def test_answers_wau_question(self, sample_usage_df):
        engine = KeywordEngine()

        response = engine.answer(
            "Quel est le WAU ?",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
            },
        )

        assert "WAU" in response
        assert "utilisateurs actifs" in response

    def test_answers_adoption_summary_question(self, sample_usage_df):
        engine = KeywordEngine()

        response = engine.answer(
            "Donne-moi les KPI d'adoption",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
            },
        )

        assert "DAU" in response
        assert "WAU" in response
        assert "MAU" in response

    def test_answers_evolution_question(self, sample_usage_df):
        engine = KeywordEngine()

        daily_kpis = pd.DataFrame(
            {
                "date": ["2026-07-01", "2026-07-30"],
                "dau_approx": [100, 150],
                "wau_approx": [400, 520],
                "mau_approx": [1000, 1250],
            }
        )

        response = engine.answer(
            "Donne-moi l'évolution sur 30 jours",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
                "daily_kpis": daily_kpis,
            },
        )

        assert "Évolution sur 2 jours" in response
        assert "100 → 150" in response
        assert "400 → 520" in response
        assert "1,000 → 1,250" in response

    def test_evolution_without_daily_kpis(self, sample_usage_df):
        response = self.engine.answer(
            "Donne-moi l'évolution sur 30 jours",
            context={
                "usage_df": sample_usage_df,
                "web_logs_df": pd.DataFrame(),
            },
        )

        assert response == "Aucune donnée d’évolution n’est disponible."

    def test_answers_adoption_summary_with_typographic_apostrophe(
      self,
      sample_usage_df,
    ):
      response = self.engine.answer(
          "Donne-moi les KPI d’adoption",
          context={
              "usage_df": sample_usage_df,
              "web_logs_df": pd.DataFrame(),
          },
      )

      assert "DAU" in response
      assert "WAU" in response
      assert "MAU" in response
                
class TestAssistantFactory:
    def test_get_assistant_returns_keyword_engine_by_default(self):
        from adoption_analytics.ai import get_assistant
        assistant = get_assistant()
        assert isinstance(assistant, KeywordEngine)
