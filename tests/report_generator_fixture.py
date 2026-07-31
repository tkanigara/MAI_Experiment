from __future__ import annotations

import time


def blocking_generator(
    _client_id,
    _period_id,
    *,
    on_stage,
    **_kwargs,
):
    on_stage("analysis_blocking_test")
    while True:
        time.sleep(0.1)


def presentation_then_block_generator(
    _client_id,
    _period_id,
    *,
    on_stage,
    on_presentation_created,
    **_kwargs,
):
    on_stage("slides_copy_template")
    on_presentation_created(
        {
            "presentation_id": "presentation-partial",
            "presentation_url": (
                "https://docs.google.com/presentation/d/"
                "presentation-partial/edit"
            ),
            "report_name": "Partial report",
        }
    )
    while True:
        time.sleep(0.1)
