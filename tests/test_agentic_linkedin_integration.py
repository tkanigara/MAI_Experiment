from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib
import json
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTIC_ROOT = PROJECT_ROOT / "agentic"
sys.path.insert(0, str(AGENTIC_ROOT))
sys.path.insert(1, str(PROJECT_ROOT))


class AgenticLinkedInIntegrationTests(unittest.TestCase):
    @staticmethod
    def connection_with_cursor(*, fetchone=None, fetchall=None):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.__exit__.return_value = False
        cursor.fetchone.return_value = fetchone
        cursor.fetchall.return_value = fetchall or []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        return connection, cursor

    def test_metadata_retrieval_enables_linkedin(self):
        retrieval = importlib.import_module("tools.retrieval")
        connection, _ = self.connection_with_cursor(
            fetchone=(
                "client-id",
                "par",
                "Prima Armada Raya",
                True,
                True,
                True,
                True,
                True,
                "period-id",
                date(2026, 7, 1),
                date(2026, 7, 31),
            )
        )

        with patch.object(retrieval, "get_connection", return_value=connection):
            result = retrieval.retrieval_metadata.invoke(
                {"client_code": "par", "report_date": "2026-07-01"}
            )

        self.assertTrue(result["linkedin"])
        self.assertEqual(result["report_period_id"], "period-id")

    def test_linkedin_overview_uses_real_schema_columns(self):
        tools = importlib.import_module("tools.retrieve_ll_data")
        connection, cursor = self.connection_with_cursor(
            fetchone=(
                "client-id",
                "period-id",
                Decimal("2691"),
                Decimal("36"),
                Decimal("1.36"),
                Decimal("38"),
                Decimal("2"),
                3,
                2,
                1,
                0,
                Decimal("42"),
                Decimal("41"),
                Decimal("1"),
                Decimal("0"),
                Decimal("1468"),
                Decimal("2778"),
                Decimal("2778"),
                Decimal("0.05"),
            )
        )

        with patch.object(tools, "get_connection", return_value=connection):
            result = tools.retrieve_socmed_overview.invoke(
                {"client_code": "par", "report_date": "2026-07-01"}
            )

        sql = cursor.execute.call_args.args[0]
        self.assertIn("so.photo_posts", sql)
        self.assertIn("so.video_posts", sql)
        self.assertIn("so.text_posts", sql)
        self.assertNotIn("so.reels_posts", sql)
        self.assertEqual(result["report_period_id"], "period-id")
        self.assertEqual(result["overview"]["total_followers"], 2691)

    def test_linkedin_analysis_uses_period_id_and_parses_list_content(self):
        fake_gemini = ModuleType("models.gemini")
        fake_gemini.llm = Mock()
        with patch.dict(sys.modules, {"models.gemini": fake_gemini}):
            sys.modules.pop("agents.linkedin_analysis", None)
            module = importlib.import_module("agents.linkedin_analysis")
        self.addCleanup(sys.modules.pop, "agents.linkedin_analysis", None)

        analysis = {
            "kpi_analysis": "KPI analysis",
            "socmed_overview_analysis": "Overview analysis",
            "followers_growth_analysis": "Growth analysis",
            "growth_performance_analysis": "Engagement analysis",
            "top_content_performance": "Top content analysis",
            "low_content_performance": "Low content analysis",
            "competitor_analysis": "Competitor analysis",
        }
        module.llm.invoke.return_value = SimpleNamespace(
            content=[{"type": "text", "text": json.dumps(analysis)}]
        )

        current_tool = SimpleNamespace(
            invoke=Mock(return_value={"success": True, "report_period_id": "period-id"})
        )
        history_followers = SimpleNamespace(invoke=Mock(return_value={"success": True}))
        history_engagement = SimpleNamespace(invoke=Mock(return_value={"success": True}))
        generic_tool = SimpleNamespace(invoke=Mock(return_value={"success": True}))

        with (
            patch.object(module, "retrieve_kpi", generic_tool),
            patch.object(module, "retrieve_socmed_overview", generic_tool),
            patch.object(module, "retrieve_followers_growth", current_tool),
            patch.object(module, "retrieve_followers_growth_history", history_followers),
            patch.object(module, "retrieve_engagement_performance", current_tool),
            patch.object(module, "retrieve_engagement_performance_history", history_engagement),
            patch.object(module, "retrieve_content_by_bucket", generic_tool),
            patch.object(module, "retrieve_competitor_analysis", generic_tool),
        ):
            state_module = importlib.import_module("CentralArch.state")
            state = state_module.State(
                request=state_module.Request(
                    user_intent="Generate report",
                    client_code="par",
                    report_date=date(2026, 7, 1),
                ),
                Metadata=state_module.MetaData(
                    client_id="client-id",
                    client_code="par",
                    client_name="Prima Armada Raya",
                    report_period_id="period-id",
                    linkedin=True,
                    loaded=True,
                ),
            )
            result = module.linkedin_analysis_agent(state)

        expected_history_args = {
            "client_code": "par",
            "current_report_period_id": "period-id",
        }
        history_followers.invoke.assert_called_once_with(expected_history_args)
        history_engagement.invoke.assert_called_once_with(expected_history_args)
        self.assertEqual(
            result["linkedin_result"].top_content_performance,
            "Top content analysis",
        )

    def test_router_routes_linkedin_without_unimplemented_threads_agent(self):
        state_module = importlib.import_module("CentralArch.state")
        router = importlib.import_module("agents.router")
        state = state_module.State(
            request=state_module.Request(user_intent="Generate report"),
            Metadata=state_module.MetaData(linkedin=True, threads=True),
        )

        result = router.router_node(state)

        self.assertEqual(result.routes, ["linkedin_analysis_agent"])

    def test_linkedin_insights_are_forwarded_to_slides(self):
        state_module = importlib.import_module("CentralArch.state")
        slides = importlib.import_module("agents.slides_generation")
        state = state_module.State(
            request=state_module.Request(user_intent="Generate report"),
            Metadata=state_module.MetaData(linkedin=True),
            linkedin_result=state_module.linkedin_result_analysis(
                kpi_analysis="LinkedIn KPI insight"
            ),
            summary_linkedin=state_module.SummaryLinkedin(
                key_summary="LinkedIn summary",
                action_plan="LinkedIn action plan",
            ),
        )

        rows = slides.state_insight_overrides(state)

        linked_in_rows = [row for row in rows if row["platform"] == "linkedin"]
        self.assertEqual(len(linked_in_rows), 3)
        self.assertEqual(
            {row["insight_key"] for row in linked_in_rows},
            {"kpi_analysis", "key_summary", "action_plan"},
        )

        from dashboard.slides_report import apply_report_insights

        mapping = {}
        apply_report_insights(mapping, rows)
        self.assertEqual(mapping["{{LK_KPI_ANALYSIS}}"], "LinkedIn KPI insight")
        self.assertEqual(mapping["{{LK_KEY_SUMMARY}}"], "LinkedIn summary")
        self.assertEqual(
            mapping["{{LK_RECOMMENDATION_1}}"],
            "LinkedIn action plan",
        )

    def test_linkedin_is_in_cache_and_data_version(self):
        cached = importlib.import_module("agents.cached_insights")
        repository = importlib.import_module("repositories.report_insights")
        cursor = MagicMock()
        cursor.fetchone.return_value = (1, None)

        version = repository._data_version(cursor, "client-id", "period-id")
        sql = cursor.execute.call_args.args[0]

        self.assertIn("linkedin", cached.RESULT_MODELS)
        self.assertIn("linkedin", cached.SUMMARY_MODELS)
        self.assertIn("SELECT updated_at FROM linkedin_reports", sql)
        self.assertEqual(version, "1:empty")


if __name__ == "__main__":
    unittest.main()
