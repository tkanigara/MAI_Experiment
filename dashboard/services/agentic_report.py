from __future__ import annotations

import importlib
import os
import sys
import threading
from pathlib import Path
from typing import Callable

from langchain_core.callbacks import BaseCallbackHandler, get_usage_metadata_callback
from sqlalchemy import text

try:
    from dashboard.config import BASE_DIR
    from dashboard.db import create_db_engine
except ModuleNotFoundError:
    from config import BASE_DIR
    from db import create_db_engine


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def report_context(client_id: str, period_id: str) -> dict:
    engine = create_db_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT c.client_code, rp.period_start
                    FROM clients c
                    JOIN report_periods rp ON rp.client_id = c.id
                    WHERE c.id = CAST(:client_id AS UUID)
                      AND rp.id = CAST(:period_id AS UUID)
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
    finally:
        engine.dispose()

    if not row:
        raise ValueError("Client or report period was not found.")
    return dict(row)


def load_agentic_graph():
    agentic_dir = Path(BASE_DIR) / "agentic"
    if not agentic_dir.exists():
        raise RuntimeError("Agentic runtime is not available in this deployment.")
    if str(agentic_dir) not in sys.path:
        sys.path.insert(0, str(agentic_dir))

    graph_module = importlib.import_module("CentralArch.graph")
    state_module = importlib.import_module("CentralArch.state")
    agentic_graph = graph_module.app
    Request = state_module.Request
    State = state_module.State

    return agentic_graph, Request, State


def _token_count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def summarize_gemini_usage(usage_by_model: dict | None) -> dict:
    models = {}
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cached_input_tokens = 0
    thinking_tokens = 0

    for model_name, raw_usage in sorted((usage_by_model or {}).items()):
        usage = dict(raw_usage or {})
        input_details = dict(usage.get("input_token_details") or {})
        output_details = dict(usage.get("output_token_details") or {})

        model_input = _token_count(usage.get("input_tokens"))
        model_output = _token_count(usage.get("output_tokens"))
        model_total = _token_count(usage.get("total_tokens"))
        model_cached = _token_count(input_details.get("cache_read"))
        model_thinking = _token_count(output_details.get("reasoning"))

        input_tokens += model_input
        output_tokens += model_output
        total_tokens += model_total
        cached_input_tokens += model_cached
        thinking_tokens += model_thinking
        models[str(model_name)] = {
            **usage,
            "input_tokens": model_input,
            "output_tokens": model_output,
            "total_tokens": model_total,
            "input_token_details": input_details,
            "output_token_details": output_details,
        }

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "cached_input_tokens": cached_input_tokens,
        "total_tokens": total_tokens,
        "models": models,
    }


def log_gemini_usage(usage: dict, status: str) -> None:
    model_names = ",".join(usage.get("models", {})) or "-"
    print(
        "[gemini_usage] "
        f"status={status} models={model_names} "
        f"input={usage.get('input_tokens', 0)} "
        f"output={usage.get('output_tokens', 0)} "
        f"thinking={usage.get('thinking_tokens', 0)} "
        f"cached_input={usage.get('cached_input_tokens', 0)} "
        f"total={usage.get('total_tokens', 0)}",
        flush=True,
    )


class ReportCancellationCallback(BaseCallbackHandler):
    raise_error = True

    def __init__(
        self,
        should_cancel: Callable[[], bool],
        on_stage: Callable[[str], None] | None,
        cancel_exception_type: type[Exception],
    ):
        self.should_cancel = should_cancel
        self.on_stage = on_stage
        self.cancel_exception_type = cancel_exception_type
        self._last_stage = ""
        self._lock = threading.Lock()

    def _checkpoint(self, stage: str | None = None) -> None:
        if self.should_cancel():
            raise self.cancel_exception_type(
                "Report generation was cancelled."
            )
        normalized_stage = str(stage or "").strip()
        if not normalized_stage or self.on_stage is None:
            return
        with self._lock:
            if normalized_stage == self._last_stage:
                return
            self._last_stage = normalized_stage
        self.on_stage(f"analysis_{normalized_stage}")
        if self.should_cancel():
            raise self.cancel_exception_type(
                "Report generation was cancelled."
            )

    def on_chain_start(self, _serialized, _inputs, **kwargs) -> None:
        metadata = dict(kwargs.get("metadata") or {})
        self._checkpoint(metadata.get("langgraph_node"))

    def on_chain_end(self, _outputs, **_kwargs) -> None:
        self._checkpoint()

    def on_llm_start(self, _serialized, _prompts, **_kwargs) -> None:
        self._checkpoint("gemini")

    def on_chat_model_start(self, _serialized, _messages, **_kwargs) -> None:
        self._checkpoint("gemini")

    def on_tool_start(self, _serialized, _input_str, **_kwargs) -> None:
        self._checkpoint()


def invoke_agentic_graph_with_usage(
    agentic_graph,
    initial_state,
    *,
    callbacks: list[BaseCallbackHandler] | None = None,
):
    with get_usage_metadata_callback() as usage_callback:
        try:
            if callbacks:
                result = agentic_graph.invoke(
                    initial_state,
                    config={"callbacks": list(callbacks)},
                )
            else:
                result = agentic_graph.invoke(initial_state)
        except Exception:
            usage = summarize_gemini_usage(usage_callback.usage_metadata)
            log_gemini_usage(usage, "failed")
            raise

    usage = summarize_gemini_usage(usage_callback.usage_metadata)
    log_gemini_usage(usage, "completed")
    return result, usage


def generate_agentic_report(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    *,
    should_cancel: Callable[[], bool] | None = None,
    on_stage: Callable[[str], None] | None = None,
    on_presentation_created: Callable[[dict], None] | None = None,
    existing_presentation_id: str | None = None,
    existing_report_name: str | None = None,
) -> dict:
    try:
        from dashboard.services.report_jobs import (
            ReportGenerationCancelledError,
        )
    except ModuleNotFoundError:
        from services.report_jobs import ReportGenerationCancelledError

    def cancellation_checkpoint() -> None:
        if should_cancel and should_cancel():
            raise ReportGenerationCancelledError(
                "Report generation was cancelled."
            )

    context = report_context(client_id, period_id)
    agentic_graph, Request, State = load_agentic_graph()
    cooperative_worker = any(
        (
            should_cancel,
            on_stage,
            on_presentation_created,
            existing_presentation_id,
        )
    )

    initial_state = State(
        request=Request(
            user_intent="Analyze social media performance and generate report",
            client_code=context["client_code"],
            report_date=context["period_start"],
            generate_slides=not cooperative_worker,
            slides_dry_run=dry_run,
            persist_insights=(
                not dry_run
                and env_bool("AGENTIC_PERSIST_INSIGHTS", True)
            ),
            reuse_cached_insights=env_bool("AGENTIC_REUSE_CACHED_INSIGHTS", False),
        )
    )
    cancellation_checkpoint()
    if on_stage:
        on_stage("analysis")
    callbacks = []
    if should_cancel:
        callbacks.append(
            ReportCancellationCallback(
                should_cancel,
                on_stage,
                ReportGenerationCancelledError,
            )
        )
    result, gemini_usage = invoke_agentic_graph_with_usage(
        agentic_graph,
        initial_state,
        callbacks=callbacks,
    )
    cancellation_checkpoint()

    if cooperative_worker:
        if on_stage:
            on_stage("slides")
        cancellation_checkpoint()

        slides_module = importlib.import_module("agents.slides_generation")
        state_after_analysis = State(**result)
        insight_overrides = slides_module.state_insight_overrides(
            state_after_analysis
        )
        try:
            from dashboard.services.slides_report import generate_report_slides
        except ModuleNotFoundError:
            from services.slides_report import generate_report_slides

        slides_result = generate_report_slides(
            client_id=client_id,
            period_id=period_id,
            dry_run=dry_run,
            insight_overrides=insight_overrides,
            existing_presentation_id=existing_presentation_id,
            existing_report_name=existing_report_name,
            on_presentation_created=on_presentation_created,
            should_cancel=should_cancel,
            on_stage=on_stage,
        )
        payload = {
            "status": "dry_run_completed" if dry_run else "completed",
            "presentation_id": slides_result.get("presentation_id"),
            "presentation_url": slides_result.get("presentation_url"),
            "report_name": slides_result.get("report_name"),
            "error": None,
        }
        for key in (
            "fast_mode",
            "filter_to_template",
            "total_duration_seconds",
        ):
            if key in slides_result:
                payload[key] = slides_result[key]
    else:
        generation = result["report_generation"]
        payload = (
            generation.model_dump()
            if hasattr(generation, "model_dump")
            else dict(generation)
        )

    if payload.get("status") == "failed":
        raise RuntimeError(payload.get("error") or "Agentic report generation failed.")

    payload["analysis_cache_hit"] = bool(result.get("analysis_cache_hit"))
    payload["source_data_version"] = result.get("analysis_data_version")
    payload["gemini_usage"] = gemini_usage
    return payload
