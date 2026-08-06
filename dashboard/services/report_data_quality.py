from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


RATE_TOLERANCE = Decimal("0.01")

PLATFORM_QUALITY_FIELDS = {
    "instagram": {
        "audience": "total_followers",
        "growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "content_types": ("reels_posts", "carousel_posts", "single_posts"),
    },
    "facebook": {
        "audience": "total_followers",
        "growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "content_types": ("reels_posts", "carousel_posts", "single_posts"),
    },
    "tiktok": {
        "audience": "total_followers",
        "growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "content_types": ("video_posts",),
    },
    "youtube": {
        "audience": "total_subscribers",
        "growth": "subscriber_growth",
        "growth_rate": "subscriber_growth_rate",
        "gained": None,
        "lost": "subscribers_lost",
        "content_types": ("shorts_posts", "long_form_posts", "live_posts"),
    },
    "linkedin": {
        "audience": "total_followers",
        "growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "content_types": ("photo_posts", "video_posts"),
    },
    "threads": {
        "audience": "total_followers",
        "growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "content_types": ("text_posts", "photo_posts", "video_posts"),
    },
}


def number_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def json_number(value: Decimal | None):
    return None if value is None else float(value)


def calculated_rate(numerator, denominator) -> Decimal | None:
    numerator_value = number_or_none(numerator)
    denominator_value = number_or_none(denominator)
    if numerator_value is None or denominator_value in (None, Decimal("0")):
        return None
    return numerator_value / denominator_value * Decimal("100")


def _month_start(value) -> date | None:
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    try:
        return date.fromisoformat(str(value)[:10]).replace(day=1)
    except (TypeError, ValueError):
        return None


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def consecutive_previous_trend(
    trends: list[dict],
    period_id: str,
) -> dict | None:
    current = next(
        (
            row
            for row in trends
            if str(row.get("source_period_id")) == str(period_id)
        ),
        None,
    )
    current_month = _month_start((current or {}).get("period_start"))
    if current_month is None:
        return None
    expected = _previous_month(current_month)
    return next(
        (
            row
            for row in trends
            if _month_start(row.get("period_start")) == expected
            and row.get("report_id")
        ),
        None,
    )


def _candidate(
    candidate_id: str,
    label: str,
    value: Decimal | None,
    formula: str,
    *,
    description: str = "",
    unavailable_reason: str = "Required data is unavailable.",
    available: bool | None = None,
) -> dict:
    is_available = value is not None and available is not False
    return {
        "id": candidate_id,
        "label": label,
        "value": json_number(value),
        "formula": formula,
        "description": description,
        "available": is_available,
        "unavailable_reason": None if is_available else unavailable_reason,
    }


def _check(
    *,
    code: str,
    title: str,
    actual,
    calculated: Decimal,
    formula: str,
    candidate_id: str,
    inputs: dict,
    tolerance: Decimal = Decimal("0"),
    message: str,
) -> dict | None:
    actual_value = number_or_none(actual)
    difference = (
        None
        if actual_value is None
        else abs(actual_value - calculated)
    )
    if difference is not None and difference <= tolerance:
        return None
    return {
        "code": code,
        "severity": "warning",
        "title": title,
        "message": message,
        "actual_value": json_number(actual_value),
        "calculated_value": json_number(calculated),
        "difference": json_number(difference),
        "formula": formula,
        "inputs": {
            key: json_number(number_or_none(value))
            for key, value in inputs.items()
        },
        "candidate_id": candidate_id,
        "can_apply": True,
    }


def _field_quality(result: dict, field_name: str) -> dict:
    return result.setdefault(
        field_name,
        {"quality_checks": [], "value_candidates": []},
    )


def _append_candidate(result: dict, field_name: str, candidate: dict) -> None:
    _field_quality(result, field_name)["value_candidates"].append(candidate)


def _append_check(result: dict, field_name: str, check: dict | None) -> None:
    if check:
        _field_quality(result, field_name)["quality_checks"].append(check)


def _related_check(
    check: dict,
    *,
    title: str,
    message: str,
    candidate_id: str | None = None,
    comparison: tuple | None = None,
) -> dict:
    related = {
        **check,
        "title": title,
        "message": message,
        "candidate_id": candidate_id,
        "can_apply": candidate_id is not None,
    }
    if comparison is not None:
        actual_value = number_or_none(comparison[0])
        calculated_value = number_or_none(comparison[1])
        related.update(
            {
                "actual_value": json_number(actual_value),
                "calculated_value": json_number(calculated_value),
                "difference": (
                    json_number(abs(actual_value - calculated_value))
                    if actual_value is not None
                    and calculated_value is not None
                    else None
                ),
            }
        )
    return related


def _historical_key(period_id, field_name: str) -> str:
    return f"historical|{period_id}|{field_name}"


def build_report_quality(
    *,
    platform: str,
    report: dict,
    trends: list[dict],
    period_id: str,
    all_content_count: int | None,
    fanpage_engagement_rate=None,
) -> dict[str, dict]:
    fields = PLATFORM_QUALITY_FIELDS[platform]
    result: dict[str, dict] = {}
    audience_field = fields["audience"]
    growth_field = fields["growth"]
    growth_rate_field = fields["growth_rate"]
    current_audience = number_or_none(report.get(audience_field))
    current_growth = number_or_none(report.get(growth_field))
    previous = consecutive_previous_trend(trends, period_id)
    previous_audience = number_or_none((previous or {}).get("audience_total"))
    period_growth = None
    growth_matches_period_delta = False

    if current_audience is not None and previous_audience is not None:
        period_growth = current_audience - previous_audience
        growth_matches_period_delta = (
            current_growth is not None and current_growth == period_growth
        )
        candidate = _candidate(
            "previous_period_delta",
            "Use previous-month difference",
            period_growth,
            "current audience - previous-month audience",
            description=(
                f"{json_number(current_audience)} - "
                f"{json_number(previous_audience)}"
            ),
        )
        _append_candidate(result, growth_field, candidate)
        period_check = _check(
                code="GROWTH_PERIOD_DELTA_MISMATCH",
                title="Growth differs from the previous-month audience change",
                actual=current_growth,
                calculated=period_growth,
                formula=candidate["formula"],
                candidate_id=candidate["id"],
                inputs={
                    "current_audience": current_audience,
                    "previous_audience": previous_audience,
                },
                message=(
                    "The current growth value does not match the difference "
                    "between this month and the immediately previous month."
                ),
            )
        if period_check:
            related_fields = [
                growth_field,
                audience_field,
                f"previous_{audience_field}",
            ]
            period_check["related_fields"] = related_fields
            _append_check(result, growth_field, period_check)

            if current_growth is not None:
                audience_candidate = _candidate(
                    "audience_from_growth",
                    "Use previous audience plus growth",
                    previous_audience + current_growth,
                    "previous-month audience + growth",
                )
                _append_candidate(
                    result,
                    audience_field,
                    audience_candidate,
                )
                _append_check(
                    result,
                    audience_field,
                    _related_check(
                        period_check,
                        title="Audience total contributes to the growth difference",
                        message=(
                            "Review this month's audience total, the growth value, "
                            "and the previous-month audience before choosing a correction."
                        ),
                        candidate_id=audience_candidate["id"],
                        comparison=(
                            current_audience,
                            previous_audience + current_growth,
                        ),
                    ),
                )

                previous_candidate = _candidate(
                    "previous_audience_from_growth",
                    "Use current audience minus growth",
                    current_audience - current_growth,
                    "current audience - growth",
                )
                historical_field = _historical_key(
                    (previous or {}).get("source_period_id"),
                    audience_field,
                )
                _append_candidate(
                    result,
                    historical_field,
                    previous_candidate,
                )
                _append_check(
                    result,
                    historical_field,
                    _related_check(
                        period_check,
                        title="Previous-month audience contributes to the growth difference",
                        message=(
                            "Changing this historical value can affect this and other "
                            "reports, so confirm the source snapshot first."
                        ),
                        candidate_id=previous_candidate["id"],
                        comparison=(
                            previous_audience,
                            current_audience - current_growth,
                        ),
                    ),
                )

    gained_field = fields["gained"]
    lost_field = fields["lost"]
    gained = number_or_none(report.get(gained_field)) if gained_field else None
    lost = number_or_none(report.get(lost_field)) if lost_field else None
    if gained is not None and lost is not None:
        flow_growth = gained - lost
        candidate = _candidate(
            "audience_flow_balance",
            "Use gained minus lost",
            flow_growth,
            "audience gained - audience lost",
            description=f"{json_number(gained)} - {json_number(lost)}",
        )
        _append_candidate(result, growth_field, candidate)
        flow_check = _check(
                code="GROWTH_FLOW_BALANCE_MISMATCH",
                title="Growth differs from gained minus lost",
                actual=current_growth,
                calculated=flow_growth,
                formula=candidate["formula"],
                candidate_id=candidate["id"],
                inputs={"audience_gained": gained, "audience_lost": lost},
                message=(
                    "Fanpage Karma may use a different snapshot window; review "
                    "the values before choosing a replacement."
                ),
            )
        if flow_check:
            related_fields = [growth_field, gained_field, lost_field]
            flow_check["related_fields"] = related_fields
            _append_check(result, growth_field, flow_check)

            if current_growth is not None:
                follows_candidate = _candidate(
                    "gained_from_growth_balance",
                    "Use growth plus lost",
                    current_growth + lost,
                    "growth + audience lost",
                    available=current_growth + lost >= 0,
                    unavailable_reason="The calculated gained value would be negative.",
                )
                _append_candidate(result, gained_field, follows_candidate)
                unfollows_candidate = _candidate(
                    "lost_from_growth_balance",
                    "Use gained minus growth",
                    gained - current_growth,
                    "audience gained - growth",
                    available=gained - current_growth >= 0,
                    unavailable_reason="The calculated lost value would be negative.",
                )
                _append_candidate(result, lost_field, unfollows_candidate)
                component_message = (
                    "Growth matches the previous-month audience change, so review "
                    "the gained/lost values or their source snapshot window."
                    if growth_matches_period_delta
                    else
                    "This field is one of the values that can cause the growth balance difference."
                )
                _append_check(
                    result,
                    gained_field,
                    _related_check(
                        flow_check,
                        title="Audience gained may contribute to the growth difference",
                        message=component_message,
                        candidate_id=follows_candidate["id"],
                        comparison=(gained, current_growth + lost),
                    ),
                )
                _append_check(
                    result,
                    lost_field,
                    _related_check(
                        flow_check,
                        title="Audience lost may contribute to the growth difference",
                        message=component_message,
                        candidate_id=unfollows_candidate["id"],
                        comparison=(lost, gained - current_growth),
                    ),
                )

    if current_growth is not None and previous_audience not in (None, Decimal("0")):
        calculated_growth_rate = (
            current_growth / previous_audience * Decimal("100")
        )
        candidate = _candidate(
            "growth_rate_previous_audience",
            "Use calculated growth rate",
            calculated_growth_rate,
            "growth / previous-month audience x 100",
        )
        _append_candidate(result, growth_rate_field, candidate)
        growth_rate_check = _check(
                code="GROWTH_RATE_MISMATCH",
                title="Growth rate differs from the monthly growth calculation",
                actual=report.get(growth_rate_field),
                calculated=calculated_growth_rate,
                formula=candidate["formula"],
                candidate_id=candidate["id"],
                inputs={
                    "growth": current_growth,
                    "previous_audience": previous_audience,
                },
                tolerance=RATE_TOLERANCE,
                message="Rates are compared with a 0.01 percentage-point tolerance.",
            )
        if growth_rate_check:
            related_fields = [
                growth_rate_field,
                growth_field,
                f"previous_{audience_field}",
            ]
            growth_rate_check["related_fields"] = related_fields
            _append_check(result, growth_rate_field, growth_rate_check)

            current_growth_rate = number_or_none(report.get(growth_rate_field))
            if current_growth_rate is not None:
                growth_candidate = _candidate(
                    "growth_from_imported_rate",
                    "Use rate-based growth",
                    current_growth_rate
                    * previous_audience
                    / Decimal("100"),
                    "imported growth rate x previous audience / 100",
                )
                _append_candidate(result, growth_field, growth_candidate)
                _append_check(
                    result,
                    growth_field,
                    _related_check(
                        growth_rate_check,
                        title="Growth contributes to the growth-rate difference",
                        message=(
                            "Review the growth count, imported rate, and previous-month "
                            "audience before choosing a correction."
                        ),
                        candidate_id=growth_candidate["id"],
                        comparison=(
                            current_growth,
                            current_growth_rate
                            * previous_audience
                            / Decimal("100"),
                        ),
                    ),
                )

                if current_growth_rate != 0:
                    previous_candidate = _candidate(
                        "previous_audience_from_growth_rate",
                        "Use growth divided by rate",
                        current_growth
                        / current_growth_rate
                        * Decimal("100"),
                        "growth / imported growth rate x 100",
                    )
                    historical_field = _historical_key(
                        (previous or {}).get("source_period_id"),
                        audience_field,
                    )
                    _append_candidate(
                        result,
                        historical_field,
                        previous_candidate,
                    )
                    _append_check(
                        result,
                        historical_field,
                        _related_check(
                            growth_rate_check,
                            title="Previous-month audience contributes to the rate difference",
                            message=(
                                "Changing this historical value can affect multiple reports. "
                                "Confirm the previous source snapshot first."
                            ),
                            candidate_id=previous_candidate["id"],
                            comparison=(
                                previous_audience,
                                current_growth
                                / current_growth_rate
                                * Decimal("100"),
                            ),
                        ),
                    )

    total_engagement = number_or_none(report.get("total_engagement"))
    rate_quality = _field_quality(result, "engagement_rate")
    fanpage_rate = number_or_none(fanpage_engagement_rate)
    rate_quality["value_candidates"].append(
        _candidate(
            "fanpage_karma_rate",
            "Fanpage Karma rate",
            fanpage_rate,
            "Imported directly from Account Data > Engagement",
            unavailable_reason="Fanpage Karma engagement rate is missing.",
        )
    )
    follower_rate = calculated_rate(total_engagement, current_audience)
    audience_label = "subscribers" if platform == "youtube" else "followers"
    rate_quality["value_candidates"].append(
        _candidate(
            "calculated_rate_by_audience",
            f"Calculated from {audience_label}",
            follower_rate,
            f"total engagement / {audience_label} x 100",
            unavailable_reason=f"Total engagement or {audience_label} is missing or zero.",
        )
    )
    reach_rate = calculated_rate(total_engagement, report.get("reach"))
    rate_quality["value_candidates"].append(
        _candidate(
            "calculated_rate_by_reach",
            "Calculated from reach",
            reach_rate,
            "total engagement / reach x 100",
            unavailable_reason="Total engagement or reach is missing or zero.",
        )
    )
    available_calculated_rates = [
        value
        for value in (follower_rate, reach_rate)
        if value is not None
    ]
    if available_calculated_rates and (
        fanpage_rate is None
        or any(
            abs(fanpage_rate - value) > RATE_TOLERANCE
            for value in available_calculated_rates
        )
    ):
        related_fields = [
            "engagement_rate",
            "total_engagement",
            audience_field,
            "reach",
        ]
        rate_check = {
            "code": "ENGAGEMENT_RATE_DEFINITION_MISMATCH",
            "severity": "warning",
            "title": "Engagement-rate definitions produce different values",
            "message": (
                "Fanpage Karma and automatically calculated rates use different denominators. "
                "Choose the definition intended for this report or enter a value manually."
            ),
            "actual_value": json_number(fanpage_rate),
            "calculated_value": None,
            "difference": None,
            "formula": "Compare imported, audience-based, and reach-based rates",
            "inputs": {
                "total_engagement": json_number(total_engagement),
                "audience": json_number(current_audience),
                "reach": json_number(number_or_none(report.get("reach"))),
            },
            "related_fields": related_fields,
            "candidate_id": None,
            "can_apply": True,
        }
        rate_quality["quality_checks"].append(rate_check)
        component_messages = {
            "total_engagement": (
                "Total engagement is the numerator for both calculated rates. "
                "Review it if both alternatives look unexpected."
            ),
            audience_field: (
                f"{audience_label.title()} is the denominator for one calculated rate. "
                "Review it together with total engagement and reach."
            ),
            "reach": (
                "Reach is the denominator for one calculated rate. Review it "
                "together with total engagement and audience size."
            ),
        }
        for related_field, component_message in component_messages.items():
            _append_check(
                result,
                related_field,
                _related_check(
                    rate_check,
                    title=(
                        f"{related_field.replace('_', ' ').title()} contributes "
                        "to the rate difference"
                    ),
                    message=component_message,
                ),
            )

    if all_content_count is not None:
        actual_post_count = number_or_none(report.get("total_posts"))
        imported_row_count = Decimal(all_content_count)
        candidate = _candidate(
            "imported_content_row_count",
            "Use imported content count",
            imported_row_count,
            "count of imported non-story content rows",
        )
        _append_candidate(result, "total_posts", candidate)
        row_count_check = _check(
                code="TOTAL_POSTS_ROW_COUNT_MISMATCH",
                title="Total posts differs from imported content rows",
                actual=actual_post_count,
                calculated=imported_row_count,
                formula=candidate["formula"],
                candidate_id=candidate["id"],
                inputs={"imported_non_story_rows": imported_row_count},
                message="Story rows are intentionally excluded from total posts.",
            )
        if row_count_check:
            row_count_check["related_fields"] = [
                "total_posts",
                "imported_non_story_rows",
            ]
            _append_check(result, "total_posts", row_count_check)

    type_values = {
        field: number_or_none(report.get(field))
        for field in fields["content_types"]
    }
    if type_values and all(value is not None for value in type_values.values()):
        type_total = sum(type_values.values(), Decimal("0"))
        candidate = _candidate(
            "content_type_sum",
            "Use content-type total",
            type_total,
            " + ".join(fields["content_types"]),
        )
        _append_candidate(result, "total_posts", candidate)
        type_check = _check(
                code="TOTAL_POSTS_TYPE_MISMATCH",
                title="Total posts differs from the content-type breakdown",
                actual=report.get("total_posts"),
                calculated=type_total,
                formula=candidate["formula"],
                candidate_id=candidate["id"],
                inputs=type_values,
                message="Review whether every post has exactly one content type.",
            )
        if type_check:
            related_fields = ["total_posts", *fields["content_types"]]
            type_check["related_fields"] = related_fields
            _append_check(result, "total_posts", type_check)
            for content_type_field in fields["content_types"]:
                _append_check(
                    result,
                    content_type_field,
                    _related_check(
                        type_check,
                        title=(
                            f"{content_type_field.replace('_', ' ').title()} may "
                            "contribute to the post-count difference"
                        ),
                        message=(
                            "This content-type count is part of the breakdown. "
                            "Review all type counts before changing one value."
                        ),
                    ),
                )

    filtered_result = {
        field_name: quality
        for field_name, quality in result.items()
        if quality["quality_checks"] or quality["value_candidates"]
    }
    for quality in filtered_result.values():
        for check in quality["quality_checks"]:
            check["issue_id"] = f"{platform}:{check['code']}"
    return filtered_result
