"""Generate Ads reports from the modular V4 Google Slides library.

Each output slide is cloned from one archetype and receives a slide-scoped
placeholder mapping. This lets the same generic placeholders be reused safely
for multiple objectives, platforms, and Ad Sets in one report.
"""

from __future__ import annotations

import os
import re
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

try:
    from dashboard.repositories.meta_ads_repository import MetaAdsRepository
    from dashboard.services.ads_objectives import METRICS, objective_definition
    from dashboard.slides_report import (
        audit_mapping, copy_template, execute_slides_batch_update,
        extract_placeholders_from_presentation, extract_presentation_id,
        get_google_services,
        resolve_project_path, share_presentation_as_editor,
    )
except ModuleNotFoundError:  # pragma: no cover
    from repositories.meta_ads_repository import MetaAdsRepository
    from services.ads_objectives import METRICS, objective_definition
    from slides_report import (
        audit_mapping, copy_template, execute_slides_batch_update,
        extract_placeholders_from_presentation, extract_presentation_id,
        get_google_services,
        resolve_project_path, share_presentation_as_editor,
    )


BASE_DIR = Path(__file__).resolve().parents[1]
ADS_TEMPLATE_FALLBACK = "1q9QqlYk81xBCPzYYNag3jGPIuAd9IncydKrQwXrzTS4"
MODEL_LABELS = {"jba": "JBA", "dunlop": "DUNLOP"}
PLATFORM_LABELS = {"meta": "All Meta", "instagram": "Instagram", "facebook": "Facebook"}
ARCHETYPE = {
    "cover": "adsv4_slide_01", "guide": "adsv4_slide_02",
    "cumulative": "adsv4_slide_03", "monthly": "adsv4_slide_04",
    "divider": "adsv4_slide_05", "creative": "adsv4_slide_06",
    "content": "adsv4_slide_07", "breakdown": "adsv4_slide_08",
    "optimization": "adsv4_slide_09", "comparison": "adsv4_slide_10",
    "adset": "adsv4_slide_11", "kpi": "adsv4_slide_14",
    "entity": "adsv4_slide_15", "distribution": "adsv4_slide_16",
    "dimension": "adsv4_slide_17", "strategy": "adsv4_slide_18",
    "platform_conclusion": "adsv4_slide_19",
    "executive": "adsv4_slide_20", "contract": "adsv4_slide_12",
    "end": "adsv4_slide_13",
}

# Only these metrics can be safely added across child rows. Reach, frequency,
# rates, and unit-cost metrics must come from the parent grain/summary instead.
ADDITIVE_METRICS = {
    "result", "impressions", "post_engagements", "engagements",
    "link_clicks", "spend", "views", "leads", "destination_clicks",
    "interactions", "shares", "saves", "reactions", "comments", "thruplay",
}


def _clean(value, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return re.sub(r"\s+", " ", str(value)).strip() or fallback


def _clip(value, limit: int = 360, fallback: str = "—") -> str:
    text = _clean(value, fallback)
    if text == fallback or len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _friendly_label(value) -> str:
    text = _clean(value)
    if text == "—":
        return text
    aliases = {
        "instagram_reels": "Instagram Reels",
        "instagram_explore": "Instagram Explore",
        "instagram_explore_grid_home": "Instagram Explore Home",
        "instagram_stories": "Instagram Stories",
        "instagram_feed": "Instagram Feed",
        "facebook_feed": "Facebook Feed",
        "facebook_profile_feed": "Facebook Profile Feed",
        "facebook_stories": "Facebook Stories",
        "instream_video": "In-stream Video",
    }
    return aliases.get(text.lower(), text.replace("_", " ").title())


def _number(value, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _clean(value, fallback)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def _metric_value(value, key: str) -> str:
    if value is None:
        return "—"
    definition = METRICS.get(key) or {}
    if definition.get("format") == "currency":
        return f"Rp {_number(value)}"
    if definition.get("format") == "percentage":
        return f"{_number(value)}%"
    return _number(value)


def _date_value(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return _clean(value)


def _datetime_value(value) -> str:
    if not value:
        return "—"
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d %b %Y, %H:%M") if parsed.tzinfo else parsed.strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError, OverflowError):
        return _clean(value)


def _set(mapping: dict[str, str], key: str, value, fallback: str = "—") -> None:
    mapping[f"{{{{{key}}}}}"] = _clean(value, fallback)


def _ratio(numerator, denominator) -> str:
    try:
        result = float(numerator) / float(denominator) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"
    return f"{_number(result)}%"


def _remaining_budget(value) -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return _metric_value(value, "spend")
    if numeric < 0:
        return f"Overspent by {_metric_value(abs(numeric), 'spend')}"
    return _metric_value(numeric, "spend")


def _metric(row: dict | None, key: str | None):
    if not row or not key:
        return None
    metrics = row.get("metrics") or row
    value = metrics.get(key)
    if value is None:
        value = {"result": metrics.get("result_value"), "post_engagements": metrics.get("engagements")}.get(key)
    return value


def _sum_rows(rows: list[dict], key: str | None):
    values = []
    for row in rows:
        value = _metric(row, key)
        if value is not None:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                pass
    return sum(values) if values else None


def _total_metric(rows: list[dict], key: str | None, parent: dict | None = None):
    """Return a valid total without summing non-additive delivery metrics."""
    parent_value = _metric(parent, key)
    if parent_value is not None:
        return parent_value
    return _sum_rows(rows, key) if key in ADDITIVE_METRICS else None


def _active_account_info(client: dict, period: dict) -> tuple[str, str, str, str]:
    accounts = {str(item.get("id")): item for item in (client.get("meta_ad_accounts") or [])}
    ids = [str(value) for value in (period.get("selected_ad_account_ids") or [])]
    selected = [accounts[item] for item in ids if item in accounts]
    names = ", ".join(_clean(item.get("name"), "Meta Ad Account") for item in selected) or "—"
    currencies = sorted({str(item.get("currency") or "").strip() for item in selected if item.get("currency")})
    timezones = sorted({str(item.get("timezone_name") or "").strip() for item in selected if item.get("timezone_name")})
    return names, ", ".join(ids) or "—", ", ".join(timezones) or "—", ", ".join(currencies) or "—"


def _metric_keys(repo: MetaAdsRepository, client_id: str, objective: str) -> list[str]:
    try:
        configs = repo.metric_configurations(client_id).get("configurations") or []
    except Exception:
        configs = []
    selected = next((row for row in configs if row.get("scope") == "meta" and row.get("objective") == objective), None)
    if selected is not None:
        return [str(key) for key in (selected.get("metric_keys") or []) if key in METRICS]
    return list(objective_definition("meta", objective).get("default_metric_keys") or [])


def _confirmed_objectives(repo: MetaAdsRepository, client_id: str, period_id: str) -> list[str]:
    result = []
    for row in repo.campaign_mappings(client_id, period_id).get("campaigns") or []:
        objective = row.get("reporting_objective")
        if row.get("is_confirmed") and row.get("is_included") and objective and objective not in result:
            result.append(objective)
    return result


def _cumulative_values(
    repo: MetaAdsRepository,
    client_id: str,
    periods: list[dict],
    current_period: dict,
    model: str,
    platform: str,
    objective: str,
) -> dict:
    """Sum like-for-like objective values through the selected period."""

    current_end = str(current_period.get("period_end") or "")
    totals = {
        "target": 0.0, "budget": 0.0, "actual": 0.0, "spend": 0.0,
        "has_target": False, "has_budget": False,
        "has_actual": False, "has_spend": False,
    }
    dimension = "adset" if model == "jba" else "creative"
    for raw_period in periods:
        historical = dict(raw_period)
        if current_end and str(historical.get("period_end") or "") > current_end:
            continue
        historical_id = str(historical.get("id") or "")
        if not historical_id:
            continue
        try:
            if objective not in _confirmed_objectives(repo, client_id, historical_id):
                continue
            analysis = repo.analysis(
                client_id,
                historical_id,
                dimension,
                {"platform_scope": platform, "objective": objective},
            )
        except Exception:
            continue
        config = (
            ((historical.get("objective_configs") or {}).get("meta") or {})
            .get(objective) or {}
        )
        values = {
            "target": config.get("target_monthly"),
            "budget": config.get("budget_monthly"),
            "actual": (analysis.get("summary") or {}).get("result"),
            "spend": (analysis.get("summary") or {}).get("spend"),
        }
        for key, value in values.items():
            if value is None:
                continue
            try:
                totals[key] += float(value)
                totals[f"has_{key}"] = True
            except (TypeError, ValueError):
                continue
    return {
        key: totals[key] if totals[f"has_{key}"] else None
        for key in ("target", "budget", "actual", "spend")
    }


def _goal_breakdown(
    repo: MetaAdsRepository,
    client_id: str,
    period_id: str,
    platform: str,
    objective: str,
) -> dict:
    """Return one scoped breakdown shared by the slides and Ads analyst."""

    platforms = [platform] if platform != "meta" else ["instagram", "facebook"]
    combined = {"placements": [], "demographics": [], "regions": []}
    for scope in platforms:
        try:
            detail = repo.platform_detail(client_id, period_id, scope)
        except Exception:
            continue
        goal = next(
            (item for item in detail.get("goals", []) if item.get("key") == objective),
            None,
        )
        if not goal:
            continue
        for key in combined:
            for raw_row in goal.get(key) or []:
                row = dict(raw_row)
                label = row.get("label") or row.get("name")
                if not label and key == "demographics":
                    label = " · ".join(
                        _clean(row.get(field), "")
                        for field in ("age", "gender")
                        if row.get(field)
                    )
                if not label and key == "regions":
                    label = row.get("region")
                label = _friendly_label(label)
                row["label"] = (
                    f"{PLATFORM_LABELS[scope]} · {label}"
                    if platform == "meta" and label != "—"
                    else label
                )
                if row.get("result") is None:
                    row["result"] = row.get("result_value")
                impressions, reach = row.get("impressions"), row.get("reach")
                if row.get("frequency") is None and impressions is not None and reach:
                    row["frequency"] = float(impressions) / float(reach)
                combined[key].append(row)
    if platform == "meta":
        try:
            shared = repo.shared_audience_breakdowns(client_id, period_id, objective)
        except Exception:
            shared = {}
        for key in ("demographics", "regions"):
            if combined[key]:
                continue
            for raw_row in shared.get(key) or []:
                row = dict(raw_row)
                label = row.get("label")
                if not label and key == "demographics":
                    label = " · ".join(
                        _clean(row.get(field), "")
                        for field in ("age", "gender")
                        if row.get(field)
                    )
                row["label"] = f"All Meta · {_friendly_label(label)}"
                if row.get("result") is None:
                    row["result"] = row.get("result_value")
                combined[key].append(row)
    return combined


def _analysis_sections(payload: dict) -> dict:
    breakdown = payload.get("breakdown") or {}
    return {
        "performance_overview": dict(payload.get("analysis", {}).get("summary") or {}),
        "content_analysis": list(payload.get("rows") or []),
        "placement_analysis": list(breakdown.get("placements") or []),
        "audience_demographic_analysis": list(breakdown.get("demographics") or []),
        "region_analysis": list(breakdown.get("regions") or []),
    }


def _payload_fingerprint(payload: dict) -> str:
    evidence = {
        "source": payload.get("source") or {},
        "objective": payload.get("objective"),
        "platform_scope": payload.get("platform_scope"),
        "sections": payload.get("analysis_sections") or _analysis_sections(payload),
    }
    encoded = json.dumps(
        evidence,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_payload(client_id: str, period_id: str, model: str, platform: str, objective: str) -> dict:
    repo = MetaAdsRepository()
    client_periods = repo.client_periods(client_id)
    client = dict(client_periods["client"])
    period = next((dict(item) for item in client_periods.get("periods", []) if str(item.get("id")) == str(period_id)), None)
    if not period:
        raise ValueError("Ads report period was not found.")
    dimension = "adset" if model == "jba" else "creative"
    analysis = repo.analysis(client_id, period_id, dimension, {"platform_scope": platform, "objective": objective})
    summary = dict(analysis.get("summary") or {})
    if summary.get("result") is None:
        derived = [_metric(row, "result") for row in analysis.get("rows") or []]
        derived = [float(value) for value in derived if value is not None]
        if derived:
            summary["result"] = sum(derived)
    analysis["summary"] = summary
    account_name, account_ids, timezone, currency = _active_account_info(client, period)
    config = ((period.get("objective_configs") or {}).get("meta") or {}).get(objective) or {}
    target, budget = config.get("target_monthly"), config.get("budget_monthly")
    actual, spend = summary.get("result"), summary.get("spend")
    warning = ""
    if analysis.get("data_status") != "ready":
        warning = "No confirmed performance rows are available for this objective."
    elif analysis.get("warnings"):
        warning = " ".join(str(item) for item in analysis["warnings"])
    breakdown = _goal_breakdown(repo, client_id, period_id, platform, objective)
    payload = {
        "repo": repo, "client": client, "period": period, "model": model,
        "platform_scope": platform, "objective": objective, "analysis": analysis,
        "metric_keys": _metric_keys(repo, client_id, objective),
        "account_name": account_name, "account_ids": account_ids,
        "timezone": timezone, "currency": currency,
        "source": analysis.get("source") or {}, "target": target, "budget": budget,
        "objective_config": config,
        "actual": actual, "spend": spend,
        "achievement": float(actual) / float(target) * 100 if actual is not None and target else None,
        "rows": list(analysis.get("rows") or []), "breakdown": breakdown,
        "warning": warning,
    }
    payload["cumulative"] = _cumulative_values(
        repo,
        client_id,
        list(client_periods.get("periods") or []),
        period,
        model,
        platform,
        objective,
    )
    payload["analysis_sections"] = _analysis_sections(payload)
    payload["evidence_fingerprint"] = _payload_fingerprint(payload)
    return payload


def _payload_with_analysis(payload: dict, dimension: str, filters: dict | None = None) -> dict:
    result = dict(payload)
    query = {"platform_scope": payload["platform_scope"], "objective": payload["objective"], **(filters or {})}
    analysis = payload["repo"].analysis(str(payload["client"]["id"]), str(payload["period"]["id"]), dimension, query)
    result.update(analysis=analysis, rows=list(analysis.get("rows") or []), source=analysis.get("source") or payload.get("source") or {})
    result["analysis_sections"] = _analysis_sections(result)
    result["evidence_fingerprint"] = _payload_fingerprint(result)
    return result


def _run_agent_analysis(payload: dict) -> dict[str, str | None]:
    """Analyse the exact frozen evidence that will populate this slide set."""

    from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import (
        run_ads_analysis_agent,
    )
    from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
        AdsRetrievalData,
        InstagramMetricAnalysis,
        MetaData,
        Request,
        State,
    )

    objective = payload["objective"]
    client = payload["client"]
    period = payload["period"]
    analysis_type = str(
        payload.get("analysis", {}).get("dimension")
        or ("adset" if payload["model"] == "jba" else "creative")
    )
    objective_payload = {
        "status": payload["analysis"].get("data_status", "ready"),
        "success": payload["analysis"].get("data_status") == "ready",
        "objective": objective,
        "analysis_type": analysis_type,
        "platform_scope": payload["platform_scope"],
        "source": payload.get("source") or {},
        "summary": payload["analysis"].get("summary") or {},
        "rows": payload.get("rows") or [],
        "display_metrics": payload["analysis"].get("display_metrics") or [],
        "available_filters": payload["analysis"].get("available_filters") or {},
        "breakdowns": {},
        # This is the same object used by the slide mapping below.  No
        # secondary API/SQL lookup occurs inside the analyst.
        "sections": payload["analysis_sections"],
        "warnings": payload["analysis"].get("warnings") or [],
        "unconfirmed_count": payload["analysis"].get("unconfirmed_count", 0),
    }
    ads_data = AdsRetrievalData(
        status="ready",
        success=True,
        client={
            "id": str(client.get("id")),
            "code": client.get("client_code"),
            "name": client.get("client_name"),
            "ads_platforms": client.get("ads_platforms") or [],
            "meta_ad_accounts": client.get("meta_ad_accounts") or [],
        },
        period={
            "id": str(period.get("id")),
            "label": period.get("period_label"),
            "start": period.get("period_start"),
            "end": period.get("period_end"),
        },
        analysis_type=objective_payload["analysis_type"],
        platform_scope=payload["platform_scope"],
        objectives=[objective],
        objective_data={objective: objective_payload},
        source=payload.get("source") or {},
    )
    state = State(
        request=Request(
            client_code=client.get("client_code"),
            period_id=str(period.get("id")),
            analysis_type=objective_payload["analysis_type"],
            platform_scope=payload["platform_scope"],
            objectives=[objective],
            include_breakdowns=True,
        ),
        Metadata=MetaData(
            client_id=str(client.get("id")),
            client_code=client.get("client_code"),
            client_name=client.get("client_name"),
            report_period_id=str(period.get("id")),
            period_start=period.get("period_start"),
            period_end=period.get("period_end"),
            loaded=True,
        ),
        ads_data=ads_data,
    )
    fields = [
        "performance_overview",
        "content_analysis",
        "placement_analysis",
        "audience_demographic_analysis",
        "region_analysis",
        "optimisation_action",
    ]
    result = run_ads_analysis_agent(
        state,
        objective=objective,
        system_prompt=None,
        result_model=InstagramMetricAnalysis,
        result_field="instagram_result",
        output_fields=fields,
        label=(
            f"{PLATFORM_LABELS.get(payload['platform_scope'], payload['platform_scope'])} "
            f"Ads {objective.replace('_', ' ').title()} report analysis"
        ),
    )["instagram_result"]
    return {field: getattr(result, field, None) for field in fields}


def _attach_agent_analysis(payloads: list[dict]) -> list[dict]:
    enabled = str(os.getenv("ADS_REPORT_AGENT_ANALYSIS_ENABLED", "true")).lower() not in {
        "0", "false", "no", "off",
    }
    if not enabled:
        return payloads
    strict = str(os.getenv("ADS_REPORT_AGENT_ANALYSIS_STRICT", "false")).lower() in {
        "1", "true", "yes", "on",
    }
    for payload in payloads:
        try:
            payload["agent_analysis"] = _run_agent_analysis(payload)
            payload["agent_evidence_fingerprint"] = payload["evidence_fingerprint"]
        except Exception as exc:
            if strict:
                raise
            payload["agent_analysis"] = {}
            payload["warning"] = " ".join(
                item for item in (
                    payload.get("warning"),
                    f"Agent analysis unavailable: {exc.__class__.__name__}.",
                ) if item
            )
    return payloads


def _default_mapping() -> dict[str, str]:
    mapping = {}
    for key in ("CLIENT_NAME", "CLIENT_LOGO", "REPORT_PERIOD", "REPORT_MODEL_LABEL", "PREPARED_BY", "DATA_SOURCE", "LAST_SYNCED_AT", "PLATFORM_LABEL", "OBJECTIVE_LABEL", "DATE_START", "DATE_END", "SLIDE_NUMBER", "CONTENT_ANALYSIS_TITLE", "NEXT_REPORT_PERIOD"):
        _set(mapping, key, "", "")
    _set(mapping, "PREPARED_BY", "MAI Ads Team")
    for index in range(1, 4):
        for suffix in ("IMAGE", "NAME", "CAMPAIGN", "ADSET", "RESULT", "SPEND", "INSIGHT", "RECOMMENDATION"):
            _set(mapping, f"BEST_CONTENT_{index}_{suffix}", "Preview unavailable" if suffix == "IMAGE" else "—")
    return mapping


def _performance_insight(payload: dict) -> str:
    agent_value = (payload.get("agent_analysis") or {}).get("performance_overview")
    if agent_value:
        return _clip(agent_value)
    rows = payload.get("rows") or []
    if not rows:
        return payload.get("warning") or "No performance rows are available."
    return f"{_clean(rows[0].get('name'))} delivered the strongest {payload['objective'].replace('_', ' ')} result in this scope."


def _base_mapping(payload: dict) -> dict[str, str]:
    mapping = _default_mapping()
    source = payload.get("source") or {}
    _set(mapping, "CLIENT_NAME", payload["client"].get("client_name"))
    _set(mapping, "REPORT_PERIOD", payload["period"].get("period_label"))
    _set(mapping, "REPORT_MODEL_LABEL", MODEL_LABELS[payload["model"]])
    _set(mapping, "PLATFORM_LABEL", PLATFORM_LABELS.get(payload["platform_scope"], payload["platform_scope"].title()))
    _set(mapping, "OBJECTIVE_LABEL", payload["objective"].replace("_", " ").title())
    _set(mapping, "DATE_START", _date_value(source.get("data_start") or payload["period"].get("period_start")))
    _set(mapping, "DATE_END", _date_value(source.get("data_end") or payload["period"].get("period_end")))
    _set(mapping, "DATA_SOURCE", "Meta API" if source.get("type") == "api" else "CSV import")
    _set(mapping, "LAST_SYNCED_AT", _datetime_value(source.get("updated_at")))
    _set(mapping, "NEXT_REPORT_PERIOD", "next reporting period")
    _set(mapping, "CONTENT_ANALYSIS_TITLE", f"TOP 3 CONTENT — {payload['objective'].replace('_', ' ').title()}")
    _set(mapping, "PERFORMANCE_INSIGHT", _performance_insight(payload))
    return mapping


def _fill_creative(mapping: dict, payload: dict) -> None:
    rows, keys = payload.get("rows") or [], (payload.get("metric_keys") or [])[:10]
    summary = payload.get("analysis", {}).get("summary") or {}
    for metric_index in range(1, 11):
        key = keys[metric_index - 1] if metric_index <= len(keys) else None
        _set(mapping, f"METRIC_{metric_index}_LABEL", (METRICS.get(key) or {}).get("label") if key else "—")
        _set(mapping, f"CREATIVE_TOTAL_METRIC_{metric_index}", _metric_value(_total_metric(rows, key, summary), key) if key else "—")
        for row_index in range(1, 6):
            row = rows[row_index - 1] if row_index <= len(rows) else None
            if metric_index == 1:
                _set(mapping, f"CREATIVE_ROW_{row_index}_NAME", row.get("name") if row else "", "")
            _set(mapping, f"CREATIVE_ROW_{row_index}_METRIC_{metric_index}", _metric_value(_metric(row, key), key) if row and key else "", "")


def _fill_content(mapping: dict, payload: dict) -> dict[str, str]:
    images = {}
    rows = (payload.get("rows") or [])[:3]
    _set(mapping, "CONTENT_ANALYSIS_TITLE", f"TOP {len(rows)} CONTENT — {payload['objective'].replace('_', ' ').title()}")
    agent = payload.get("agent_analysis") or {}
    for index, row in enumerate(rows, 1):
        metrics = row.get("metrics") or {}
        _set(mapping, f"BEST_CONTENT_{index}_NAME", row.get("name"))
        _set(mapping, f"BEST_CONTENT_{index}_CAMPAIGN", row.get("campaign_name"))
        _set(mapping, f"BEST_CONTENT_{index}_ADSET", row.get("adset_name"))
        _set(mapping, f"BEST_CONTENT_{index}_RESULT", _metric_value(metrics.get("result"), "result"))
        _set(mapping, f"BEST_CONTENT_{index}_SPEND", _metric_value(metrics.get("spend"), "spend"))
        evidence = (
            f"Ranked #{index}: {_metric_value(metrics.get('result'), 'result')} results "
            f"from {_metric_value(metrics.get('spend'), 'spend')} spend."
        )
        _set(
            mapping,
            f"BEST_CONTENT_{index}_INSIGHT",
            _clip(agent.get("content_analysis"), 320) if index == 1 and agent.get("content_analysis") else evidence,
        )
        _set(
            mapping,
            f"BEST_CONTENT_{index}_RECOMMENDATION",
            _clip(agent.get("optimisation_action"), 260)
            if index == 1 and agent.get("optimisation_action")
            else "Compare this creative against the other eligible rows using the same objective metrics.",
        )
        url = row.get("thumbnail_url") or row.get("image_url")
        if url:
            images[f"{{{{BEST_CONTENT_{index}_IMAGE}}}}"] = str(url)
    return images


def _fill_breakdown(mapping: dict, payload: dict, kind: str) -> None:
    source_keys = {"placement": "placements", "demographic": "demographics", "region": "regions"}
    titles = {"placement": "PLACEMENT ANALYSIS", "demographic": "AUDIENCE DEMOGRAPHICS", "region": "REGION BREAKDOWN"}
    dimensions = {"placement": "Placement", "demographic": "Audience", "region": "Region"}
    rows = payload.get("breakdown", {}).get(source_keys[kind]) or []
    keys = (payload.get("metric_keys") or [])[:7]
    _set(mapping, "BREAKDOWN_TYPE_LABEL", titles[kind]); _set(mapping, "BREAKDOWN_TITLE", titles[kind]); _set(mapping, "BREAKDOWN_DIMENSION_LABEL", dimensions[kind])
    for metric_index in range(1, 8):
        key = keys[metric_index - 1] if metric_index <= len(keys) else None
        _set(mapping, f"BREAKDOWN_METRIC_{metric_index}_LABEL", (METRICS.get(key) or {}).get("label") if key else "—")
        _set(mapping, f"BREAKDOWN_TOTAL_METRIC_{metric_index}", _metric_value(_total_metric(rows, key), key) if key else "—")
        for row_index in range(1, 7):
            row = rows[row_index - 1] if row_index <= len(rows) else None
            if metric_index == 1:
                label = (row or {}).get("label") or (row or {}).get("name")
                if not label and row:
                    label = " · ".join(_clean(row.get(field), "") for field in ("age", "gender") if row.get(field))
                _set(mapping, f"BREAKDOWN_ROW_{row_index}_LABEL", _friendly_label(label) if label else "")
            _set(mapping, f"BREAKDOWN_ROW_{row_index}_METRIC_{metric_index}", _metric_value(_metric(row, key), key) if row and key else "", "")
    agent_field = {
        "placement": "placement_analysis",
        "demographic": "audience_demographic_analysis",
        "region": "region_analysis",
    }[kind]
    agent_value = (payload.get("agent_analysis") or {}).get(agent_field)
    _set(
        mapping,
        "BREAKDOWN_INSIGHT",
        _clip(agent_value) if agent_value else f"No supported {dimensions[kind].lower()} conclusion is available for this scope.",
    )


def _fill_kpi(mapping: dict, payload: dict) -> None:
    summary = payload["analysis"].get("summary") or {}
    cards = [("Primary Result", payload.get("actual"), "result"), ("Reach", summary.get("reach"), "reach"), ("Spend", payload.get("spend"), "spend"), ("Cost / Result", summary.get("cost_per_result"), "cost_per_result")]
    for index, (label, value, key) in enumerate(cards, 1):
        _set(mapping, f"KPI_{index}_LABEL", label); _set(mapping, f"KPI_{index}_VALUE", _metric_value(value, key))
    _set(mapping, "OBJECTIVE_ACHIEVEMENT", f"{_number(payload.get('achievement'))}%" if payload.get("achievement") is not None else "—")
    _set(mapping, "OBJECTIVE_TARGET", _metric_value(payload.get("target"), "result")); _set(mapping, "OBJECTIVE_ACTUAL", _metric_value(payload.get("actual"), "result"))
    _set(mapping, "OBJECTIVE_BUDGET_USE", _ratio(payload.get("spend"), payload.get("budget"))); _set(mapping, "OBJECTIVE_BUDGET", _metric_value(payload.get("budget"), "spend")); _set(mapping, "OBJECTIVE_SPEND", _metric_value(payload.get("spend"), "spend"))
    _set(mapping, "OBJECTIVE_SUMMARY_INSIGHT", _performance_insight(payload))


def _fill_comparison(mapping: dict, payload: dict) -> None:
    rows = payload.get("rows") or []
    target_rows = {
        str(item.get("adset_id")): item
        for item in (payload.get("objective_config") or {}).get("adset_targets") or []
        if item.get("adset_id")
    }
    for column in range(1, 5):
        row = rows[column - 1] if column <= len(rows) else None
        label = ""
        if row:
            label = f"{_clean(row.get('name'))} · {_clean(row.get('campaign_name'))}"
        _set(mapping, f"COMPARE_COL_{column}_LABEL", _clip(label, 90, ""), "")
    cost_key = "cpc" if payload.get("objective") == "link_clicks" else "cost_per_result"
    comparison_metrics = [
        (payload.get("objective", "result").replace("_", " ").title(), "result"),
        ("Reach", "reach"),
        ("Impressions", "impressions"),
        ("Link Clicks", "link_clicks"),
        ("CTR", "ctr"),
        ((METRICS.get(cost_key) or {}).get("label", "Cost / Result"), cost_key),
        ("Spend / Budget", "spend_budget"),
        ("Achievement vs. KPI", "achievement"),
    ]
    for metric_index, (label, key) in enumerate(comparison_metrics, 1):
        _set(mapping, f"COMPARE_METRIC_{metric_index}_LABEL", label)
        for column in range(1, 5):
            row = rows[column - 1] if column <= len(rows) else None
            value = ""
            if row:
                target = target_rows.get(str(row.get("id"))) or {}
                if key == "spend_budget":
                    value = f"{_metric_value(_metric(row, 'spend'), 'spend')} / {_metric_value(target.get('budget'), 'spend')}"
                elif key == "achievement":
                    value = _ratio(_metric(row, "result"), target.get("target"))
                else:
                    value = _metric_value(_metric(row, key), key)
            _set(mapping, f"COMPARE_ROW_{metric_index}_COL_{column}", value, "")
    _set(mapping, "OBJECTIVE_COMPARISON_INSIGHT", _performance_insight(payload))


def _fill_adset(mapping: dict, payload: dict, adset: dict) -> None:
    rows, keys = payload.get("rows") or [], (payload.get("metric_keys") or [])[:8]
    adset_name = _clean(adset.get("name"), "Ad Set")
    _set(mapping, "ADSET_NAME", f"{adset_name} · {_clean(adset.get('campaign_name'))}")
    for metric_index in range(1, 9):
        key = keys[metric_index - 1] if metric_index <= len(keys) else None
        _set(mapping, f"AD_METRIC_{metric_index}_LABEL", (METRICS.get(key) or {}).get("label") if key else "—")
        _set(mapping, f"AD_TOTAL_METRIC_{metric_index}", _metric_value(_total_metric(rows, key, adset), key) if key else "—")
        for row_index in range(1, 6):
            row = rows[row_index - 1] if row_index <= len(rows) else None
            if metric_index == 1:
                _set(mapping, f"AD_ROW_{row_index}_NAME", row.get("name") if row else "", ""); _set(mapping, f"AD_ROW_{row_index}_ADSET", row.get("adset_name") if row else "", "")
            _set(mapping, f"AD_ROW_{row_index}_METRIC_{metric_index}", _metric_value(_metric(row, key), key) if row and key else "", "")
    _set(mapping, "ADSET_PERFORMANCE_INSIGHT", f"Top creative: {_clean(rows[0].get('name') if rows else None)}.")


def _fill_optimization(mapping: dict, payload: dict) -> None:
    top = _clean((payload.get("rows") or [{}])[0].get("name"))
    agent = payload.get("agent_analysis") or {}
    _set(mapping, "OPTIMIZATION_WHAT_WORKED", _clip(agent.get("performance_overview")) if agent.get("performance_overview") else f"{top} delivered the strongest result for this objective.")
    risk = agent.get("placement_analysis") or agent.get("audience_demographic_analysis") or payload.get("warning")
    _set(mapping, "OPTIMIZATION_RISK", _clip(risk) if risk else "No supported placement or audience risk was identified from the available breakdowns.")
    action = _clip(agent.get("optimisation_action")) if agent.get("optimisation_action") else "Retain the strongest setup as control and test one audience or creative variable at a time."
    _set(mapping, "OPTIMIZATION_NEXT_STEP", action)
    _set(mapping, "OPTIMIZATION_PRIORITY", action)


def _fill_overview(mapping: dict, payloads: list[dict], prefix: str) -> None:
    _set(mapping, "CUMULATIVE_PERIOD_LABEL", f"Through {payloads[0]['period'].get('period_label')}")
    overview_sources = [
        (payload.get("cumulative") or {}) if prefix == "CUMULATIVE" else payload
        for payload in payloads
    ]
    for row_index in range(1, 8):
        payload = payloads[row_index - 1] if row_index <= len(payloads) else None
        source = overview_sources[row_index - 1] if row_index <= len(overview_sources) else None
        values = {suffix: "—" for suffix in ("CHANNEL", "EST_RESULT", "KPI_LABEL", "ACTUAL", "ACHIEVEMENT", "BUDGET", "SPENT", "BUDGET_USE", "REMAINING_BUDGET")}
        if payload and source is not None:
            budget, spend = source.get("budget"), source.get("spend")
            target, actual = source.get("target"), source.get("actual")
            try:
                remaining = float(budget) - float(spend) if budget is not None and spend is not None else None
            except (TypeError, ValueError):
                remaining = None
            values.update(
                CHANNEL=f"{PLATFORM_LABELS[payload['platform_scope']]} - {payload['objective'].replace('_', ' ').title()}",
                EST_RESULT=_metric_value(target, "result"),
                KPI_LABEL=payload["objective"].replace("_", " ").title(),
                ACTUAL=_metric_value(actual, "result"),
                ACHIEVEMENT=_ratio(actual, target),
                BUDGET=_metric_value(budget, "spend"),
                SPENT=_metric_value(spend, "spend"),
                BUDGET_USE=_ratio(spend, budget),
                REMAINING_BUDGET=_remaining_budget(remaining),
            )
        for suffix, value in values.items():
            _set(mapping, f"{prefix}_ROW_{row_index}_{suffix}", value)
    budget = sum(float(source.get("budget") or 0) for source in overview_sources)
    spend = sum(float(source.get("spend") or 0) for source in overview_sources)
    # Primary results and KPI targets have different units across objectives
    # (for example Reach, Leads, and Link Clicks).  Do not manufacture one
    # cross-objective total or achievement percentage.
    totals = {
        "EST_RESULT": "—",
        "KPI_LABEL": "Multiple units",
        "ACTUAL": "—",
        "ACHIEVEMENT": "—",
        "BUDGET": _metric_value(budget, "spend"),
        "SPENT": _metric_value(spend, "spend"),
        "BUDGET_USE": _ratio(spend, budget),
        "REMAINING_BUDGET": _remaining_budget(budget - spend),
    }
    for suffix, value in totals.items(): _set(mapping, f"{prefix}_TOTAL_{suffix}", value)
    _set(mapping, "OVERVIEW_INSIGHT", "Performance is grouped by platform and confirmed reporting objective.")


def _fill_platform_conclusion(mapping: dict, payloads: list[dict]) -> None:
    campaigns = {
        str(row.get("campaign_id") or row.get("campaign_name"))
        for payload in payloads for row in payload.get("rows") or []
        if row.get("campaign_id") or row.get("campaign_name")
    }
    adsets = {
        str(row.get("adset_id") or row.get("adset_name") or row.get("id"))
        for payload in payloads for row in payload.get("rows") or []
        if row.get("adset_id") or row.get("adset_name") or row.get("id")
    }
    spend = sum(float(p.get("spend") or 0) for p in payloads)
    cards = [
        ("Objectives", len({p["objective"] for p in payloads}), "result"),
        ("Campaigns", len(campaigns), "result"),
        ("Ad Sets", len(adsets), "result"),
        ("Spend", spend, "spend"),
    ]
    for index, (label, value, key) in enumerate(cards, 1): _set(mapping, f"PLATFORM_SUMMARY_METRIC_{index}_LABEL", label); _set(mapping, f"PLATFORM_SUMMARY_METRIC_{index}_VALUE", _metric_value(value, key))
    evidence = [
        _clip((p.get("agent_analysis") or {}).get("performance_overview"), 220)
        for p in payloads if (p.get("agent_analysis") or {}).get("performance_overview")
    ]
    actions = [
        _clip((p.get("agent_analysis") or {}).get("optimisation_action"), 220)
        for p in payloads if (p.get("agent_analysis") or {}).get("optimisation_action")
    ]
    _set(mapping, "PLATFORM_CONCLUSION_WIN", " ".join(evidence[:2]) or "Each objective is evaluated using its own primary-result unit and KPI.")
    _set(mapping, "PLATFORM_CONCLUSION_RISK", "Primary results are not added or ranked across objectives because their units differ.")
    _set(mapping, "PLATFORM_CONCLUSION_NEXT_ACTION", " ".join(actions[:2]) or "Review each objective against its own target before reallocating budget.")


def _fill_executive(mapping: dict, payloads: list[dict]) -> None:
    campaigns = {
        str(row.get("campaign_id") or row.get("campaign_name"))
        for payload in payloads for row in payload.get("rows") or []
        if row.get("campaign_id") or row.get("campaign_name")
    }
    adsets = {
        str(row.get("adset_id") or row.get("adset_name") or row.get("id"))
        for payload in payloads for row in payload.get("rows") or []
        if row.get("adset_id") or row.get("adset_name") or row.get("id")
    }
    spend = sum(float(p.get("spend") or 0) for p in payloads)
    cards = [
        ("Objectives", len({p["objective"] for p in payloads}), "result"),
        ("Campaigns", len(campaigns), "result"),
        ("Ad Sets", len(adsets), "result"),
        ("Spend", spend, "spend"),
    ]
    for index, (label, value, key) in enumerate(cards, 1): _set(mapping, f"EXEC_METRIC_{index}_LABEL", label); _set(mapping, f"EXEC_METRIC_{index}_VALUE", _metric_value(value, key))
    evidence = [
        _clip((p.get("agent_analysis") or {}).get("performance_overview"), 220)
        for p in payloads if (p.get("agent_analysis") or {}).get("performance_overview")
    ]
    actions = [
        _clip((p.get("agent_analysis") or {}).get("optimisation_action"), 220)
        for p in payloads if (p.get("agent_analysis") or {}).get("optimisation_action")
    ]
    _set(mapping, "EXECUTIVE_KEY_WINS", " ".join(evidence[:2]) or "Objective-level performance is detailed in the report using comparable metrics within each objective.")
    _set(mapping, "EXECUTIVE_RISKS", "Cross-objective Results, Reach, and Achievement are intentionally not combined because the units or audiences can overlap.")
    _set(mapping, "EXECUTIVE_NEXT_PRIORITIES", " ".join(actions[:2]) or "Use objective-level KPI achievement and cost efficiency for the next allocation decision.")


def build_ads_mapping(payload: dict, *, slide_number: str = "") -> dict[str, str]:
    """Public mapping helper retained for tests and agent integrations."""
    mapping = _base_mapping(payload); _set(mapping, "SLIDE_NUMBER", slide_number, "")
    # Model names describe the layout choice; client-facing content slides
    # always identify the actual client.
    _set(mapping, "REPORT_MODEL_LABEL", payload["client"].get("client_name"))
    _fill_creative(mapping, payload); _fill_content(mapping, payload); _fill_kpi(mapping, payload)
    _fill_comparison(mapping, payload); _fill_optimization(mapping, payload)
    _fill_platform_conclusion(mapping, [payload]); _fill_executive(mapping, [payload])
    return mapping


def _slide_plan(payloads: list[dict], model: str) -> list[dict]:
    first = payloads[0]; common = _base_mapping(first)
    client_label = _clean(first["client"].get("client_name"))
    cumulative = dict(common); _set(cumulative, "REPORT_MODEL_LABEL", client_label); _fill_overview(cumulative, payloads, "CUMULATIVE")
    monthly = dict(common); _set(monthly, "REPORT_MODEL_LABEL", client_label); _fill_overview(monthly, payloads, "MONTHLY")
    plans = [{"source": ARCHETYPE["cover"], "mapping": common, "images": {}}, {"source": ARCHETYPE["cumulative"], "mapping": cumulative, "images": {}}, {"source": ARCHETYPE["monthly"], "mapping": monthly, "images": {}}]
    by_platform = {}
    for payload in payloads: by_platform.setdefault(payload["platform_scope"], []).append(payload)
    for platform_payloads in by_platform.values():
        for payload in platform_payloads:
            mapping = build_ads_mapping(payload)
            _set(mapping, "REPORT_MODEL_LABEL", client_label)
            plans.append({"source": ARCHETYPE["divider"], "mapping": mapping, "images": {}})
            if model == "dunlop":
                plans.append({"source": ARCHETYPE["creative"], "mapping": mapping, "images": {}})
                if payload.get("rows"):
                    content = dict(mapping); images = _fill_content(content, payload)
                    plans.append({"source": ARCHETYPE["content"], "mapping": content, "images": images})
                for kind in ("placement", "demographic", "region"):
                    source_key = {"placement": "placements", "demographic": "demographics", "region": "regions"}[kind]
                    if not (payload.get("breakdown") or {}).get(source_key):
                        continue
                    detail = dict(mapping); _fill_breakdown(detail, payload, kind)
                    plans.append({"source": ARCHETYPE["breakdown"], "mapping": detail, "images": {}})
                plans.append({"source": ARCHETYPE["optimization"], "mapping": mapping, "images": {}})
            else:
                plans.append({"source": ARCHETYPE["kpi"], "mapping": mapping, "images": {}})
                plans.append({"source": ARCHETYPE["comparison"], "mapping": mapping, "images": {}})
                creative_payload = _payload_with_analysis(payload, "creative")
                if "agent_analysis" in payload:
                    _attach_agent_analysis([creative_payload])
                content = build_ads_mapping(creative_payload); images = _fill_content(content, creative_payload)
                for adset in (payload.get("rows") or [])[:4]:
                    detail_payload = _payload_with_analysis(payload, "creative", {"adset_ids": [adset.get("id")]})
                    detail = build_ads_mapping(detail_payload); _fill_adset(detail, detail_payload, adset)
                    plans.append({"source": ARCHETYPE["adset"], "mapping": detail, "images": {}})
                if creative_payload.get("rows"):
                    plans.append({"source": ARCHETYPE["content"], "mapping": content, "images": images})
                if (payload.get("breakdown") or {}).get("regions"):
                    region = dict(mapping); _fill_breakdown(region, payload, "region")
                    plans.append({"source": ARCHETYPE["breakdown"], "mapping": region, "images": {}})
                plans.append({"source": ARCHETYPE["optimization"], "mapping": mapping, "images": {}})
        conclusion = _base_mapping(platform_payloads[0]); _set(conclusion, "REPORT_MODEL_LABEL", client_label); _fill_platform_conclusion(conclusion, platform_payloads)
        plans.append({"source": ARCHETYPE["platform_conclusion"], "mapping": conclusion, "images": {}})
    executive = _base_mapping(first); _set(executive, "REPORT_MODEL_LABEL", client_label); _fill_executive(executive, payloads)
    plans.extend([{"source": ARCHETYPE["executive"], "mapping": executive, "images": {}}, {"source": ARCHETYPE["end"], "mapping": common, "images": {}}])
    for index, plan in enumerate(plans, 1):
        plan["slide_id"] = f"adsout_{index:03d}"; plan["mapping"] = {**plan["mapping"], "{{SLIDE_NUMBER}}": str(index)}
    return plans


def _source_placeholders(presentation: dict) -> dict[str, set[str]]:
    return {slide.get("objectId"): extract_placeholders_from_presentation({"slides": [slide]}) for slide in presentation.get("slides") or []}


def _chunks(items: list, size: int):
    for index in range(0, len(items), size): yield items[index:index + size]


def _assemble_slides(slides_service, presentation_id: str, plans: list[dict]) -> dict:
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    current_ids = [slide.get("objectId") for slide in presentation.get("slides") or []]
    output_ids = [plan["slide_id"] for plan in plans]
    if ARCHETYPE["cover"] in current_ids:
        stale = [item for item in current_ids if item and item.startswith("adsout_")]
        if stale: execute_slides_batch_update(slides_service, presentation_id, [{"deleteObject": {"objectId": item}} for item in stale])
        duplicates = [{"duplicateObject": {"objectId": plan["source"], "objectIds": {plan["source"]: plan["slide_id"]}}} for plan in plans]
        for batch in _chunks(duplicates, 40): execute_slides_batch_update(slides_service, presentation_id, batch)
        originals = [item for item in current_ids if item and not item.startswith("adsout_")]
        execute_slides_batch_update(slides_service, presentation_id, [{"deleteObject": {"objectId": item}} for item in originals])
        moves = [{"updateSlidesPosition": {"slideObjectIds": [slide_id], "insertionIndex": index}} for index, slide_id in enumerate(output_ids)]
        for batch in _chunks(moves, 40): execute_slides_batch_update(slides_service, presentation_id, batch)
        return {"assembled": True, "slide_count": len(plans)}
    if all(slide_id in current_ids for slide_id in output_ids):
        return {"assembled": False, "resumed": True, "slide_count": len(plans)}
    raise RuntimeError("Existing Ads presentation is not a V4 library or a resumable generated report.")


def _replace_scoped(slides_service, presentation_id: str, plans: list[dict], placeholders_by_source: dict[str, set[str]]) -> dict:
    image_success, image_failures = set(), []
    for plan in plans:
        for placeholder, url in plan.get("images", {}).items():
            request = {"replaceAllShapesWithImage": {"imageUrl": url, "replaceMethod": "CENTER_INSIDE", "containsText": {"text": placeholder, "matchCase": True}, "pageObjectIds": [plan["slide_id"]]}}
            try:
                execute_slides_batch_update(slides_service, presentation_id, [request]); image_success.add((plan["slide_id"], placeholder))
            except Exception as exc:
                image_failures.append({"slide_id": plan["slide_id"], "placeholder": placeholder, "error": exc.__class__.__name__})
    requests = []
    for plan in plans:
        mapping = plan["mapping"]
        for key in sorted(placeholders_by_source.get(plan["source"], set())):
            if (plan["slide_id"], key) in image_success: continue
            requests.append({"replaceAllText": {"containsText": {"text": key, "matchCase": True}, "replaceText": str(mapping.get(key, "—")), "pageObjectIds": [plan["slide_id"]]}})
    changed = 0
    for batch in _chunks(requests, int(os.getenv("SLIDES_TEXT_BATCH_SIZE", "100"))):
        response = execute_slides_batch_update(slides_service, presentation_id, batch)
        changed += sum(int(reply.get("replaceAllText", {}).get("occurrencesChanged", 0)) for reply in response.get("replies") or [])
    return {"requests": len(requests), "occurrences_changed": changed, "image_replacements": len(image_success), "image_failures": image_failures}


def generate_ads_slides_report(client_id: str, period_id: str, dry_run: bool = False, report_model: str = "jba", platform_scope: str | None = None, objective: str | None = None, existing_presentation_id: str | None = None, existing_report_name: str | None = None, on_presentation_created: Callable[[dict], None] | None = None, should_cancel: Callable[[], bool] | None = None, on_stage: Callable[[str], None] | None = None) -> dict:
    def stage(value: str) -> None:
        if should_cancel and should_cancel(): raise RuntimeError("Report generation was cancelled.")
        if on_stage: on_stage(value)
    load_dotenv(BASE_DIR / ".env")
    model = str(report_model or "jba").strip().lower()
    if model not in MODEL_LABELS: raise ValueError("Ads report model must be jba or dunlop.")
    requested_scope = str(platform_scope or "meta").strip().lower()
    if requested_scope not in PLATFORM_LABELS: raise ValueError("Ads platform scope must be All Meta, Instagram, or Facebook.")
    repo = MetaAdsRepository(); objectives = _confirmed_objectives(repo, client_id, period_id)
    if objective:
        requested = str(objective).strip().lower(); objectives = [requested] if requested in objectives else []
    if not objectives: raise ValueError("Confirm at least one included Campaign objective before generating the report.")
    scopes = ["instagram", "facebook"] if model == "dunlop" and requested_scope == "meta" else [requested_scope]
    payloads = [_build_payload(client_id, period_id, model, scope, objective_key) for scope in scopes for objective_key in objectives]
    if not dry_run:
        stage("ads_agent_analysis")
        _attach_agent_analysis(payloads)
    plans = _slide_plan(payloads, model)
    template_id = extract_presentation_id(os.getenv("ADS_SLIDES_TEMPLATE_ID") or os.getenv("META_ADS_SLIDES_TEMPLATE_ID") or ADS_TEMPLATE_FALLBACK)
    stage("ads_template_scan")
    slides_service, drive_service = get_google_services(resolve_project_path(os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")), resolve_project_path(os.getenv("GOOGLE_TOKEN_FILE", "token.json")), int(os.getenv("GOOGLE_OAUTH_PORT", "0")))
    template = slides_service.presentations().get(presentationId=template_id).execute()
    placeholders_by_source = _source_placeholders(template)
    # Audit only archetypes that will survive in the generated report. The V4
    # library intentionally contains unused Google/TikTok/search archetypes,
    # so auditing the entire library would report false missing placeholders.
    used_placeholders = set().union(*(placeholders_by_source.get(plan["source"], set()) for plan in plans))
    combined_mapping = {}
    for plan in plans:
        combined_mapping.update(plan["mapping"])
    for placeholder in used_placeholders:
        combined_mapping.setdefault(placeholder, "—")
    audit = audit_mapping(used_placeholders, combined_mapping, {"payloads": payloads})
    if dry_run:
        return {"status": "dry_run_completed", "template_id": template_id, "client_id": client_id, "period_id": period_id, "report_model": model, "platform_scope": requested_scope, "objectives": objectives, "slide_count": len(plans), "slide_plan": [{"slide_id": plan["slide_id"], "source": plan["source"]} for plan in plans], "mapping": combined_mapping, "audit": audit, "evidence_fingerprints": [p["evidence_fingerprint"] for p in payloads]}
    report_name = str(existing_report_name or "").strip() or f"{MODEL_LABELS[model]} Ads Report - {payloads[0]['client'].get('client_name')} - {payloads[0]['period'].get('period_label')}"
    stage("ads_copy_template")
    presentation_id, created = (existing_presentation_id, False) if existing_presentation_id else (copy_template(drive_service, template_id, report_name), True)
    if created and on_presentation_created: on_presentation_created({"presentation_id": presentation_id, "presentation_url": f"https://docs.google.com/presentation/d/{presentation_id}/edit", "report_name": report_name})
    stage("ads_share_presentation"); share_presentation_as_editor(drive_service, presentation_id)
    stage("ads_assemble_slides"); assembly = _assemble_slides(slides_service, presentation_id, plans)
    stage("ads_replace_placeholders"); replacement = _replace_scoped(slides_service, presentation_id, plans, placeholders_by_source)
    return {"status": "completed", "presentation_id": presentation_id, "presentation_url": f"https://docs.google.com/presentation/d/{presentation_id}/edit", "report_name": report_name, "template_id": template_id, "report_model": model, "platform_scope": requested_scope, "objectives": objectives, "slide_count": len(plans), "audit": audit, "assembly": assembly, "replacement": replacement, "created": created, "evidence_fingerprints": [p["evidence_fingerprint"] for p in payloads], "agent_evidence_fingerprints": [p.get("agent_evidence_fingerprint") for p in payloads], "evidence_consistent": all(p.get("agent_evidence_fingerprint") == p.get("evidence_fingerprint") for p in payloads if p.get("agent_analysis")), "agent_analysis_used": any(bool(p.get("agent_analysis")) for p in payloads)}
