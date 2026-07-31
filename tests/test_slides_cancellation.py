from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import slides_report
from dashboard.services.report_jobs import ReportGenerationCancelledError


class FakeRequest:
    def __init__(self, *, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.calls = 0

    def execute(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return dict(self.response)


class FakeFiles:
    def __init__(self, requests):
        self.requests = list(requests)
        self.updates = []

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self.requests.pop(0)


class FakeDrive:
    def __init__(self, requests):
        self.files_api = FakeFiles(requests)

    def files(self):
        return self.files_api


class SlidesCancellationTests(unittest.TestCase):
    def test_long_retry_sleep_is_interrupted_immediately(self):
        token = slides_report._REPORT_CANCEL_CHECK.set(lambda: True)
        try:
            with self.assertRaises(ReportGenerationCancelledError):
                slides_report.interruptible_sleep(65)
        finally:
            slides_report._REPORT_CANCEL_CHECK.reset(token)

    def test_cancelled_presentation_is_moved_to_trash(self):
        drive = FakeDrive(
            [
                FakeRequest(
                    response={
                        "id": "presentation-1",
                        "name": "Report 1",
                        "trashed": True,
                    }
                )
            ]
        )
        with (
            patch.object(
                slides_report,
                "resolve_project_path",
                return_value=Path(__file__),
            ),
            patch.object(
                slides_report,
                "get_google_services",
                return_value=(Mock(), drive),
            ),
        ):
            result = slides_report.cleanup_cancelled_presentation(
                "presentation-1",
                "Report 1",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "trashed")
        self.assertEqual(
            drive.files_api.updates[0]["body"],
            {"trashed": True},
        )

    def test_cleanup_falls_back_to_cancelled_rename(self):
        drive = FakeDrive(
            [
                FakeRequest(error=PermissionError("cannot trash")),
                FakeRequest(
                    response={
                        "id": "presentation-1",
                        "name": "[CANCELED] Report 1",
                        "trashed": False,
                    }
                ),
            ]
        )
        with (
            patch.object(
                slides_report,
                "resolve_project_path",
                return_value=Path(__file__),
            ),
            patch.object(
                slides_report,
                "get_google_services",
                return_value=(Mock(), drive),
            ),
        ):
            result = slides_report.cleanup_cancelled_presentation(
                "presentation-1",
                "Report 1",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "renamed")
        self.assertEqual(
            drive.files_api.updates[1]["body"],
            {"name": "[CANCELED] Report 1"},
        )


if __name__ == "__main__":
    unittest.main()
