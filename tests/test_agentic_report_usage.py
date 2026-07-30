from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.services.agentic_report import (
    invoke_agentic_graph_with_usage,
    summarize_gemini_usage,
)


class AgenticReportUsageTests(unittest.TestCase):
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
