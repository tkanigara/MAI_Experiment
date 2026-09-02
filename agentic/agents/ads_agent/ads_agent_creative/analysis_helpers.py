"""Shared helpers for Ads objective agents.

The objective-specific modules stay intentionally thin: retrieval is already
available on ``state.ads_data`` and only the prompt/result schema differs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Type

from agentic.models.gemini import llm
from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_sections,
)
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langchain_core.messages import HumanMessage, SystemMessage


DEFAULT_SYSTEM_PROMPT = """
You are an Ads performance analyst. Analyse only the supplied dashboard data.
Return valid JSON with exactly the requested keys. Keep unavailable values
explicitly null and do not invent metrics, campaigns, or conclusions.

Use the supplied analysis_sections as the source for each output field:
- performance_overview(_<objective>) uses performance_overview;
- content_analysis(_<objective>) uses content_analysis;
- placement_analysis(_<objective>) uses placement_analysis;
- audience_demographic_analysis(_<objective>) uses audience_demographic_analysis;
- region_analysis(_<objective>) uses region_analysis.
The optimisation_action(_<objective>) must be grounded in those sections and
the objective metrics. If a section is empty or the needed metric is absent,
return null for that field instead of guessing. Do not treat an empty
breakdown as zero performance.
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
    # Models occasionally leave a trailing comma in an otherwise valid JSON
    # object.  This is the same tolerant parsing behavior used by Social Media.
    return re.sub(r",(\s*[}\]])", r"\1", text)


def run_ads_analysis_agent(
    state: State,
    *,
    system_prompt: str | None,
    result_model: Type[Any],
    result_field: str,
    output_fields: list[str],
    label: str,
) -> dict[str, Any]:
    """Run one objective analysis using the already-loaded Ads state."""

    base = {
        "client_code": state.Metadata.client_code or state.request.client_code,
        "objective": state.ads_data.objective or state.request.objective,
    }
    if state.ads_data.status != "ready":
        # Do not ask the model to hallucinate an explanation when retrieval did
        # not produce ready data (including source mismatch, unconfirmed
        # mappings, and coming-soon platforms).  The UI/consumer can inspect
        # status and warnings.
        return {result_field: result_model(**base)}

    payload = state.ads_data.model_dump(mode="json")
    sections = payload.get("sections") or retrieve_ads_sections(payload)
    # ``sections`` is the agent-facing projection. Avoid sending the nested
    # entity-keyed breakdowns twice, which can unnecessarily inflate Gemini's
    # context when a report has many creatives.
    dashboard_context = dict(payload)
    dashboard_context.pop("breakdowns", None)
    dashboard_context.pop("sections", None)
    context = {
        "analysis": label,
        "request": state.request.model_dump(mode="json"),
        "ads_data": dashboard_context,
        "analysis_sections": sections,
        "required_output_keys": output_fields,
    }
    messages = [
        SystemMessage(content=(system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(context, indent=2, default=str)),
    ]
    response = llm.invoke(messages)
    text = _llm_text(response)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} agent returned invalid JSON: {text[:500]}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{label} agent must return a JSON object.")
    base.update({field: result.get(field) for field in output_fields})
    return {result_field: result_model(**base)}
