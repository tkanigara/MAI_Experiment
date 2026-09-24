"""Compatibility helper for objective analysis from frozen dashboard evidence.

The report generator owns retrieval.  This helper deliberately analyses only
the sections embedded in ``state.ads_data`` so the narrative and slide numbers
always refer to the same snapshot.
"""

from __future__ import annotations

import json
import re
from typing import Any, Type

from langchain_core.messages import HumanMessage, SystemMessage

from agentic.models.gemini import llm
from agentic.utils.llm_retry import invoke_with_rate_limit_retry, transient_error_message
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


DEFAULT_SYSTEM_PROMPT = """
You are an Ads performance analyst. Analyse only the supplied dashboard data.
Return valid JSON with exactly the requested keys. Every key must contain one
analysis string or null. Do not invent metrics, campaigns, audiences, causes,
or recommendations. If the evidence needed for a section is empty, return
null for that section. Do not interpret missing data as zero performance.
""".strip()


def _llm_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    text = str(content or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _normalise_objective(objective: str) -> str:
    return str(objective or "").strip().lower().replace(" ", "_")


def _normalise_analysis_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def run_ads_analysis_agent(
    state: State,
    *,
    objective: str,
    system_prompt: str | None,
    result_model: Type[Any],
    result_field: str,
    output_fields: list[str],
    label: str,
) -> dict[str, Any]:
    """Analyse one objective without issuing another dashboard request."""

    objective = _normalise_objective(objective)
    base = {
        "client_code": state.Metadata.client_code or state.request.client_code,
        "objective": objective,
    }
    if state.ads_data.status != "ready":
        return {result_field: result_model(**base)}

    objective_data = state.ads_data.objective_data.get(objective)
    if not objective_data or objective_data.get("status") != "ready":
        return {result_field: result_model(**base)}

    sections = objective_data.get("sections") or {}
    context = {
        "analysis": label,
        "objective": objective,
        "request": state.request.model_dump(mode="json"),
        "ads_data": {
            key: objective_data.get(key)
            for key in (
                "status",
                "objective",
                "analysis_type",
                "platform_scope",
                "source",
                "unconfirmed_count",
                "warnings",
            )
            if key in objective_data
        },
        "analysis_sections": sections,
        "required_output_keys": output_fields,
    }
    messages = [
        SystemMessage(content=(system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(context, indent=2, default=str)),
    ]
    try:
        response = invoke_with_rate_limit_retry(llm, messages, label=label)
    except Exception as exc:
        safe_error = transient_error_message(exc)
        if safe_error is None:
            raise
        base["analysis_error"] = safe_error
        return {result_field: result_model(**base)}

    text = _llm_text(response)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} agent returned invalid JSON: {text[:500]}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{label} agent must return a JSON object.")

    base.update(
        {field: _normalise_analysis_value(result.get(field)) for field in output_fields}
    )
    return {result_field: result_model(**base)}
