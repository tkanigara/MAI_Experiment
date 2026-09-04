"""Shared helpers for Ads objective agents.

The objective-specific modules stay intentionally thin: retrieval is already
available on ``state.ads_data`` and only the prompt/result schema differs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Type

from langchain_core.messages import HumanMessage, SystemMessage

from agentic.models.gemini import llm
from agentic.utils.llm_retry import (
    invoke_with_rate_limit_retry,
    transient_error_message,
)
from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_sections,
)
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


DEFAULT_SYSTEM_PROMPT = """
You are an Ads performance analyst. Analyse only the supplied dashboard data.
Return valid JSON with exactly the requested keys. Keep unavailable values
explicitly null and do not invent metrics, campaigns, or conclusions.

Every requested key must contain either one analysis STRING or null. Never
return a nested object, array, raw dashboard row, or raw metric dictionary as
the value of an output key.

Use the supplied analysis_sections as the source for each output field:
- performance_overview(_<objective>) uses performance_overview;
- content_analysis(_<objective>) uses content_analysis;
- placement_analysis(_<objective>) uses placement_analysis;
- audience_demographic_analysis(_<objective>) uses audience_demographic_analysis;
- region_analysis(_<objective>) uses region_analysis.

The optimisation_action(_<objective>) must be grounded in those sections and
the objective metrics.

If a section is empty or the needed metric is absent, return null for that
field instead of guessing.

Do not treat an empty breakdown as zero performance.
""".strip()


def _llm_text(response: Any) -> str:
    """Normalize an LLM response into plain text."""

    content = getattr(response, "content", response)

    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
        )

    text = str(content or "").strip()

    # Remove Markdown JSON fences if Gemini returns them.
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    # Tolerate trailing commas in JSON.
    return re.sub(
        r",(\s*[}\]])",
        r"\1",
        text,
    )


def _normalise_objective(objective: str) -> str:
    """Normalize an objective into the canonical internal key."""

    return (
        str(objective or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )


def _normalise_analysis_value(value: Any) -> str | None:
    """Keep the state contract stable when an LLM returns structured data."""

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
    """Run one objective analysis using objective-specific Ads data.

    ``objective`` identifies which entry inside
    ``state.ads_data.objective_data`` should be analysed.

    Example:

        run_ads_analysis_agent(
            state,
            objective="reach",
            ...
        )

    will consume:

        state.ads_data.objective_data["reach"]
    """

    objective = _normalise_objective(objective)

    # ------------------------------------------------------------------
    # Base result
    # ------------------------------------------------------------------

    base = {
        "client_code": (
            state.Metadata.client_code
            or state.request.client_code
        ),
        "objective": objective,
    }

    # ------------------------------------------------------------------
    # Validate retrieval status
    # ------------------------------------------------------------------

    if state.ads_data.status != "ready":
        # Retrieval did not produce usable data.
        #
        # Do not ask the LLM to explain missing data because that can
        # introduce hallucinated conclusions.
        return {
            result_field: result_model(**base)
        }

    # ------------------------------------------------------------------
    # Retrieve data for THIS objective only
    # ------------------------------------------------------------------

    objective_data = (
        state.ads_data.objective_data.get(objective)
    )

    if not objective_data:
        # The requested objective was not retrieved.
        return {
            result_field: result_model(**base)
        }

    # Objective itself may have failed even though another objective
    # succeeded.
    if objective_data.get("status") != "ready":
        return {
            result_field: result_model(**base)
        }

    # ------------------------------------------------------------------
    # Build objective-specific sections
    # ------------------------------------------------------------------

    sections = (
        objective_data.get("sections")
        or retrieve_ads_sections(objective_data)
    )

    # ------------------------------------------------------------------
    # Build LLM-facing dashboard context
    # ------------------------------------------------------------------

    # ``sections`` already contains the actual metrics, rows and breakdowns.
    # Only retain metadata here so the same potentially large data is not sent
    # to Gemini twice for every platform/objective call.
    dashboard_context = {
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
    }

    context = {
        "analysis": label,

        "objective": objective,

        "request": state.request.model_dump(
            mode="json"
        ),

        "ads_data": dashboard_context,

        "analysis_sections": sections,

        "required_output_keys": output_fields,
    }

    # ------------------------------------------------------------------
    # Invoke LLM
    # ------------------------------------------------------------------

    messages = [
        SystemMessage(
            content=(
                (system_prompt or "").strip()
                or DEFAULT_SYSTEM_PROMPT
            )
        ),
        HumanMessage(
            content=json.dumps(
                context,
                indent=2,
                default=str,
            )
        ),
    ]

    try:
        response = invoke_with_rate_limit_retry(
            llm,
            messages,
            label=label,
        )
    except Exception as exc:
        safe_error = transient_error_message(exc)
        if safe_error is None:
            raise
        print(f"{label} skipped after retries: {safe_error}")
        base["analysis_error"] = safe_error
        return {result_field: result_model(**base)}

    text = _llm_text(response)

    # ------------------------------------------------------------------
    # Parse LLM JSON
    # ------------------------------------------------------------------

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} agent returned invalid JSON: "
            f"{text[:500]}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            f"{label} agent must return a JSON object."
        )

    # ------------------------------------------------------------------
    # Build final result model
    # ------------------------------------------------------------------

    base.update(
        {
            field: _normalise_analysis_value(result.get(field))
            for field in output_fields
        }
    )

    return {
        result_field: result_model(**base)
    }
