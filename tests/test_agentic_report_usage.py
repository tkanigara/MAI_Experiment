from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.services.agentic_report import (
    generate_agentic_report,
    invoke_agentic_graph_with_usage,
    summarize_gemini_usage,
)


class AgenticReportUsageTests(unittest.TestCase):
    def test_worker_mode_separates_analysis_from_slides(self):
        class FlexibleModel:
            def __init__(self, **values):
                for key, value in values.items():
                    setattr(self, key, value)

        graph = Mock()
        graph_result = {
            "analysis_cache_hit": False,
            "analysis_data_version": "version-1",
        }
        stages = []
        slides_module = SimpleNamespace(
            state_insight_overrides=lambda state: [
                {"platform": "instagram", "insight_key": "key_summary"}
            ]
        )

        with (
            patch(
                "dashboard.services.agentic_report.report_context",
                return_value={
                    "client_code": "client-code",
                    "period_start": "2026-07-01",
                },
            ),
            patch(
                "dashboard.services.agentic_report.load_agentic_graph",
                return_value=(graph, FlexibleModel, FlexibleModel),
            ),
            patch(
                "dashboard.services.agentic_report.invoke_agentic_graph_with_usage",
                return_value=(graph_result, {"total_tokens": 100}),
            ) as invoke_graph,
            patch(
                "dashboard.services.slides_report.generate_report_slides",
                return_value={
                    "presentation_id": "presentation-1",
                    "presentation_url": "https://slides/presentation-1",
                    "report_name": "Report 1",
                },
            ) as generate_slides,
            patch(
                "dashboard.services.agentic_report.importlib.import_module",
                return_value=slides_module,
            ),
        ):
            result = generate_agentic_report(
                "client-1",
                "period-1",
                should_cancel=lambda: False,
                on_stage=stages.append,
            )

        initial_state = invoke_graph.call_args.args[1]
        self.assertFalse(initial_state.request.generate_slides)
        self.assertEqual(stages, ["analysis", "slides"])
        self.assertEqual(result["presentation_id"], "presentation-1")
        self.assertEqual(result["source_data_version"], "version-1")
        generate_slides.assert_called_once()
        self.assertEqual(
            generate_slides.call_args.kwargs["insight_overrides"][0][
                "platform"
            ],
            "instagram",
        )

    def test_summarizes_usage_across_models(self):
        usage = summarize_gemini_usage(
            {
                "gemini-model-a": {
                    "input_tokens": 1_000,
                    "output_tokens": 200,
                    "total_tokens": 1_200,
                    "input_token_details": {"cache_read": 100},
                    "output_token_details": {"reasoning": 30},
                },
                "gemini-model-b": {
                    "input_tokens": 500,
                    "output_tokens": 75,
                    "total_tokens": 575,
                },
            }
        )

        self.assertEqual(usage["input_tokens"], 1_500)
        self.assertEqual(usage["output_tokens"], 275)
        self.assertEqual(usage["thinking_tokens"], 30)
        self.assertEqual(usage["cached_input_tokens"], 100)
        self.assertEqual(usage["total_tokens"], 1_775)
        self.assertEqual(
            set(usage["models"]),
            {"gemini-model-a", "gemini-model-b"},
        )

    def test_empty_usage_returns_zero_totals(self):
        usage = summarize_gemini_usage({})

        self.assertEqual(
            usage,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "cached_input_tokens": 0,
                "total_tokens": 0,
                "models": {},
            },
        )

    def test_wraps_complete_graph_run_with_usage_callback(self):
        callback = SimpleNamespace(
            usage_metadata={
                "gemini-3.1-flash-lite": {
                    "input_tokens": 900,
                    "output_tokens": 100,
                    "total_tokens": 1_000,
                }
            }
        )

        @contextmanager
        def fake_usage_callback():
            yield callback

        graph = Mock()
        graph.invoke.return_value = {"report_generation": {"status": "completed"}}

        with (
            patch(
                "dashboard.services.agentic_report.get_usage_metadata_callback",
                fake_usage_callback,
            ),
            patch("dashboard.services.agentic_report.print"),
        ):
            result, usage = invoke_agentic_graph_with_usage(
                graph,
                {"request": "state"},
            )

        graph.invoke.assert_called_once_with({"request": "state"})
        self.assertEqual(result["report_generation"]["status"], "completed")
        self.assertEqual(usage["input_tokens"], 900)
        self.assertEqual(usage["output_tokens"], 100)
        self.assertEqual(usage["total_tokens"], 1_000)


if __name__ == "__main__":
    unittest.main()
