from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preview_report_charts import render_audience_and_growth_chart


class ReportChartTransparencyTests(unittest.TestCase):
    def test_exported_chart_has_a_transparent_canvas(self):
        rows = [
            {
                "period_start": date(2026, 6, 1),
                "audience_total": 12500,
                "net_growth": 320,
            },
            {
                "period_start": date(2026, 7, 1),
                "audience_total": 13100,
                "net_growth": 600,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "audience_growth.png"
            figure = render_audience_and_growth_chart(
                rows,
                "PAR",
                "instagram",
                output_path,
            )
            plt.close(figure)

            with Image.open(output_path) as image:
                self.assertEqual(image.mode, "RGBA")
                alpha = image.getchannel("A")
                width, height = image.size
                corners = (
                    alpha.getpixel((0, 0)),
                    alpha.getpixel((width - 1, 0)),
                    alpha.getpixel((0, height - 1)),
                    alpha.getpixel((width - 1, height - 1)),
                )

                self.assertEqual(corners, (0, 0, 0, 0))
                self.assertIsNotNone(alpha.getbbox())


if __name__ == "__main__":
    unittest.main()
