from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator
from sqlalchemy import text

from dashboard.db import create_db_engine


PLATFORMS = {
    "instagram": {
        "table": "instagram_reports",
        "audience": "Followers",
        "audience_total": "total_followers",
        "net_growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "impressions": "r.impressions",
        "reach": "r.reach",
        "visibility_label": "Impressions",
    },
    "facebook": {
        "table": "facebook_reports",
        "audience": "Followers",
        "audience_total": "total_followers",
        "net_growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "impressions": "r.impressions",
        "reach": "r.reach",
        "visibility_label": "Impressions",
    },
    "tiktok": {
        "table": "tiktok_reports",
        "audience": "Followers",
        "audience_total": "total_followers",
        "net_growth": "follower_growth",
        "growth_rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "impressions": "r.total_views",
        "reach": "r.reach",
        "visibility_label": "Views",
    },
    "youtube": {
        "table": "youtube_reports",
        "audience": "Subscribers",
        "audience_total": "total_subscribers",
        "net_growth": "subscriber_growth",
        "growth_rate": "subscriber_growth_rate",
        "gained": None,
        "lost": "subscribers_lost",
        "impressions": "r.total_views",
        "reach": "r.reach",
        "visibility_label": "Views",
    },
}

COLORS = {
    "ink": "#20242A",
    "muted": "#667085",
    "grid": "#E4E7EC",
    "blue": "#356D9A",
    "teal": "#2A8C82",
    "red": "#C45A55",
    "gold": "#C9962E",
    "gray": "#98A2B3",
}

QUADRANT_COLORS = (
    "#356D9A",
    "#2A8C82",
    "#C9962E",
    "#C45A55",
    "#7A6FA8",
    "#68737D",
)

PLATFORM_COLORS = {
    "instagram": "#C13584",
    "facebook": "#1877F2",
    "tiktok": "#20242A",
    "youtube": "#E53935",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate local PNG previews for social media report charts."
    )
    parser.add_argument("--client-code", required=True, help="Client code, e.g. par")
    parser.add_argument(
        "--platform",
        default="instagram",
        choices=[*PLATFORMS, "all"],
        help="Platform to render. Use 'all' for every connected platform.",
    )
    parser.add_argument(
        "--month",
        help="Selected report month in YYYY-MM format. Defaults to the latest month.",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Number of months shown, from 1 to 12. Default: 6.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/chart_previews"),
        help="Root output directory.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open chart windows after saving the PNG files.",
    )
    return parser.parse_args()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip()).strip("-")
    return normalized.lower() or "report"


def number(value):
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def values(rows: list[dict], key: str) -> list[float]:
    return [number(row.get(key)) for row in rows]


def available(series: list[float]) -> bool:
    return any(not math.isnan(value) for value in series)


def connected_platforms(client: dict) -> list[str]:
    return [
        platform
        for platform in PLATFORMS
        if bool(client.get(f"has_{platform}"))
    ]


def fetch_context(engine, client_code: str, month: str | None):
    with engine.connect() as conn:
        client = conn.execute(
            text(
                """
                SELECT id, client_code, client_name,
                       has_instagram, has_facebook, has_tiktok, has_youtube
                FROM clients
                WHERE lower(client_code) = lower(:client_code)
                  AND is_active
                """
            ),
            {"client_code": client_code},
        ).mappings().first()
        if not client:
            raise ValueError(f"Client code '{client_code}' was not found.")

        period_filter = "AND to_char(period_start, 'YYYY-MM') = :month" if month else ""
        period = conn.execute(
            text(
                f"""
                SELECT id, period_label, period_start, period_end
                FROM report_periods
                WHERE client_id = :client_id
                  {period_filter}
                ORDER BY period_start DESC
                LIMIT 1
                """
            ),
            {"client_id": client["id"], "month": month},
        ).mappings().first()
        if not period:
            suffix = f" for {month}" if month else ""
            raise ValueError(f"No report period found{suffix}.")

    return dict(client), dict(period)


def fetch_trends(
    engine,
    client_id: str,
    period_start,
    platform: str,
    month_count: int,
) -> list[dict]:
    config = PLATFORMS[platform]
    table_name = config["table"]
    audience_total = config["audience_total"]
    net_growth = config["net_growth"]
    growth_rate = config["growth_rate"]
    gained = config["gained"]
    lost = config["lost"]
    impressions = config["impressions"]
    reach = config["reach"]

    gained_expression = f"r.{gained}" if gained else "NULL"
    completeness_fields = [
        f"r.{audience_total}",
        f"r.{net_growth}",
        f"r.{growth_rate}",
        f"r.{lost}",
        impressions,
        reach,
        "r.total_posts",
        "r.total_engagement",
        "r.engagement_rate",
        "r.likes",
        "r.comments",
        "r.shares",
    ]
    if gained:
        completeness_fields.append(f"r.{gained}")
    completeness_score = " + ".join(
        f"CASE WHEN {field} IS NOT NULL THEN 1 ELSE 0 END"
        for field in completeness_fields
    )
    query = text(
        f"""
        WITH periods AS (
            SELECT id, period_label, period_start
            FROM report_periods
            WHERE client_id = :client_id
              AND period_start <= :period_start
            ORDER BY period_start DESC
            LIMIT :month_count
        ),
        ranked_reports AS (
            SELECT
                r.*,
                ROW_NUMBER() OVER (
                    PARTITION BY r.report_period_id
                    ORDER BY
                        (r.profile_id IS NOT NULL) DESC,
                        ({completeness_score}) DESC,
                        r.updated_at DESC,
                        r.created_at DESC
                ) AS report_rank
            FROM {table_name} r
            JOIN periods p ON p.id = r.report_period_id
            WHERE r.client_id = :client_id
        )
        SELECT
            p.period_label,
            p.period_start,
            r.{audience_total} AS audience_total,
            r.{net_growth} AS net_growth,
            r.{growth_rate} AS audience_growth_rate,
            {gained_expression} AS audience_gained,
            r.{lost} AS audience_lost,
            {impressions} AS impressions,
            {reach} AS reach,
            r.total_posts,
            r.total_engagement,
            r.engagement_rate,
            r.likes,
            r.comments,
            r.shares
        FROM periods p
        LEFT JOIN ranked_reports r
            ON r.report_period_id = p.id
           AND r.report_rank = 1
        ORDER BY p.period_start ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "client_id": client_id,
                "period_start": period_start,
                "month_count": month_count,
            },
        ).mappings()
        return [dict(row) for row in rows]


def normalized_profile_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def is_client_profile(profile_name: str, self_names: set[str]) -> bool:
    candidate = normalized_profile_name(profile_name)
    if not candidate:
        return False
    for self_name in self_names:
        if candidate == self_name:
            return True
        if len(self_name) >= 5 and (
            candidate in self_name or self_name in candidate
        ):
            return True
    return False


def fetch_competitor_rows(
    engine,
    client: dict,
    period: dict,
    platform: str,
) -> list[dict]:
    with engine.connect() as conn:
        profile_names = [
            row["profile_name"]
            for row in conn.execute(
                text(
                    """
                    SELECT profile_name
                    FROM client_social_profiles
                    WHERE client_id = :client_id
                      AND platform = :platform
                      AND is_active = TRUE
                    """
                ),
                {
                    "client_id": client["id"],
                    "platform": platform,
                },
            ).mappings()
        ]
        rows = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT profile_name, total_followers,
                           follower_growth_rate, engagement_rate,
                           total_posts, total_engagement
                    FROM competitor_profile_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND platform = :platform
                    ORDER BY total_engagement DESC NULLS LAST,
                             total_followers DESC NULLS LAST
                    LIMIT 20
                    """
                ),
                {
                    "client_id": client["id"],
                    "period_id": period["id"],
                    "platform": platform,
                },
            ).mappings()
        ]

    self_names = {
        normalized_profile_name(value)
        for value in (
            client.get("client_code"),
            client.get("client_name"),
            *profile_names,
        )
        if normalized_profile_name(value)
    }
    return [
        row
        for row in rows
        if not is_client_profile(row["profile_name"], self_names)
    ][:3]


def compact_number(value, _position=None):
    if value is None or math.isnan(float(value)):
        return "-"
    absolute = abs(float(value))
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def style_axis(axis, *, zero_line=False):
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(COLORS["grid"])
    axis.spines["bottom"].set_color(COLORS["grid"])
    axis.tick_params(colors=COLORS["muted"], labelsize=9)
    axis.grid(axis="y", color=COLORS["grid"], linewidth=0.8, alpha=0.8)
    axis.set_axisbelow(True)
    if zero_line:
        axis.axhline(0, color=COLORS["ink"], linewidth=0.9)


def no_data(axis, message="Data belum tersedia"):
    axis.text(
        0.5,
        0.5,
        message,
        transform=axis.transAxes,
        ha="center",
        va="center",
        color=COLORS["muted"],
        fontsize=11,
    )


def annotate_points(axis, x_values, y_values, color):
    for x_value, y_value in zip(x_values, y_values):
        if math.isnan(y_value):
            continue
        axis.annotate(
            compact_number(y_value),
            (x_value, y_value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=color,
        )


def create_chart_figure(title: str, subtitle: str):
    fig, axis = plt.subplots(figsize=(10, 5.625), facecolor="white")
    fig.suptitle(
        title,
        x=0.07,
        y=0.95,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=COLORS["ink"],
    )
    fig.text(
        0.07,
        0.89,
        subtitle,
        color=COLORS["muted"],
        fontsize=10,
    )
    fig.subplots_adjust(left=0.09, right=0.94, bottom=0.14, top=0.72)
    return fig, axis


def save_chart(fig, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    return fig


def chart_context(rows: list[dict], client_name: str):
    labels = [row["period_start"].strftime("%b %Y") for row in rows]
    x_values = list(range(len(rows)))
    subtitle = f"{client_name} | Last {len(rows)} report month(s)"
    return labels, x_values, subtitle


def render_audience_and_growth_chart(
    rows: list[dict],
    client_name: str,
    platform: str,
    output_path: Path,
):
    config = PLATFORMS[platform]
    labels, x_values, subtitle = chart_context(rows, client_name)
    totals = values(rows, "audience_total")
    net_growth = values(rows, "net_growth")
    fig, axis = create_chart_figure(
        f"{platform.title()} {config['audience']} and Net Growth",
        subtitle,
    )
    style_axis(axis)
    axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
    axis.set_xticks(x_values, labels)
    axis.set_xlim(-0.5, len(rows) - 0.5)

    handles = []
    if available(totals):
        audience_line = axis.plot(
            x_values,
            totals,
            color=COLORS["blue"],
            linewidth=2.8,
            marker="o",
            markersize=7,
            label=f"Total {config['audience']}",
            zorder=3,
        )[0]
        annotate_points(axis, x_values, totals, COLORS["blue"])
        valid_totals = [value for value in totals if not math.isnan(value)]
        minimum, maximum = min(valid_totals), max(valid_totals)
        padding = max((maximum - minimum) * 0.25, maximum * 0.01, 1)
        axis.set_ylim(max(0, minimum - padding), maximum + padding)
        handles.append(audience_line)

    growth_axis = axis.twinx()
    growth_axis.spines["top"].set_visible(False)
    growth_axis.spines["right"].set_color(COLORS["grid"])
    growth_axis.tick_params(colors=COLORS["muted"], labelsize=9)
    growth_axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
    growth_axis.axhline(0, color=COLORS["grid"], linewidth=0.9, zorder=0)
    if available(net_growth):
        growth_values = [
            0 if math.isnan(value) else value
            for value in net_growth
        ]
        bar_colors = [
            COLORS["teal"] if value >= 0 else COLORS["red"]
            for value in growth_values
        ]
        growth_bars = growth_axis.bar(
            x_values,
            growth_values,
            width=0.46,
            color=bar_colors,
            alpha=0.78,
            label="Net Growth",
            zorder=1,
        )
        valid_growth = [
            value
            for value in net_growth
            if not math.isnan(value)
        ]
        growth_min = min(valid_growth)
        growth_max = max(valid_growth)
        if growth_min < 0 < growth_max:
            growth_limit = max(abs(growth_min), abs(growth_max)) * 1.35
            growth_axis.set_ylim(-growth_limit, growth_limit)
        elif growth_max <= 0:
            growth_axis.set_ylim(min(growth_min * 1.3, -1), 0)
        else:
            growth_axis.set_ylim(0, max(growth_max * 1.3, 1))

        for index, bar in enumerate(growth_bars):
            value = net_growth[index]
            if math.isnan(value):
                label = "N/A"
            elif value > 0:
                label = f"+{compact_number(value)}"
            else:
                label = compact_number(value)
            height = bar.get_height()
            growth_axis.annotate(
                label,
                (bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5 if height >= 0 else -7),
                textcoords="offset points",
                ha="center",
                va="bottom" if height >= 0 else "top",
                fontsize=8,
                color=COLORS["ink"],
                fontweight="semibold",
            )
        handles.append(growth_bars)

    if not available(totals) and not available(net_growth):
        no_data(axis)
    if handles:
        axis.legend(
            handles,
            [handle.get_label() for handle in handles],
            frameon=False,
            loc="lower left",
            bbox_to_anchor=(0, 1.03),
            borderaxespad=0,
            fontsize=9,
            ncol=2,
        )
    return save_chart(fig, output_path)


def render_impressions_reach_chart(
    rows: list[dict],
    client_name: str,
    platform: str,
    output_path: Path,
):
    config = PLATFORMS[platform]
    labels, x_values, subtitle = chart_context(rows, client_name)
    impressions = values(rows, "impressions")
    reach = values(rows, "reach")
    fig, axis = create_chart_figure(
        f"{platform.title()} {config['visibility_label']} and Reach",
        subtitle,
    )
    style_axis(axis)
    axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
    axis.set_xticks(x_values, labels)
    axis.set_xlim(-0.5, len(rows) - 0.5)
    if available(impressions) or available(reach):
        if available(impressions):
            axis.plot(
                x_values,
                impressions,
                color=COLORS["gray"],
                linewidth=2.4,
                marker="o",
                markersize=6,
                label=config["visibility_label"],
            )
            annotate_points(axis, x_values, impressions, COLORS["muted"])
        if available(reach):
            axis.plot(
                x_values,
                reach,
                color=COLORS["blue"],
                linewidth=2.8,
                marker="o",
                markersize=6,
                label="Total Reach",
            )
            annotate_points(axis, x_values, reach, COLORS["blue"])
        axis.legend(
            frameon=False,
            loc="lower left",
            bbox_to_anchor=(0, 1.03),
            borderaxespad=0,
            fontsize=9,
            ncol=2,
        )
    else:
        no_data(axis)
    return save_chart(fig, output_path)


def render_engagement_breakdown_chart(
    rows: list[dict],
    client_name: str,
    platform: str,
    output_path: Path,
):
    labels, x_values, subtitle = chart_context(rows, client_name)
    metric_specs = (
        ("Likes", values(rows, "likes"), COLORS["blue"]),
        ("Comments", values(rows, "comments"), COLORS["teal"]),
        ("Shares", values(rows, "shares"), COLORS["gold"]),
    )
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(10, 5.625),
        facecolor="white",
    )
    fig.suptitle(
        f"{platform.title()} Engagement Breakdown",
        x=0.07,
        y=0.95,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=COLORS["ink"],
    )
    fig.text(
        0.07,
        0.89,
        f"{subtitle} | Independent scale per metric",
        color=COLORS["muted"],
        fontsize=10,
    )
    fig.subplots_adjust(
        left=0.07,
        right=0.97,
        bottom=0.19,
        top=0.73,
        wspace=0.3,
    )

    for axis, (metric_label, series, color) in zip(axes, metric_specs):
        style_axis(axis)
        axis.set_title(
            metric_label,
            loc="left",
            fontsize=11,
            fontweight="semibold",
            color=COLORS["ink"],
            pad=12,
        )
        axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
        axis.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
        axis.set_xticks(x_values, labels, rotation=30, ha="right")
        axis.set_xlim(-0.5, len(rows) - 0.5)

        if not available(series):
            no_data(axis)
            continue

        plot_values = [
            0 if math.isnan(value) else value
            for value in series
        ]
        bars = axis.bar(
            x_values,
            plot_values,
            width=0.58,
            color=color,
        )
        valid_values = [
            value
            for value in series
            if not math.isnan(value)
        ]
        maximum = max(valid_values, default=0)
        axis.set_ylim(0, max(maximum * 1.22, 1))

        for index, bar in enumerate(bars):
            value = series[index]
            label = "N/A" if math.isnan(value) else compact_number(value)
            axis.annotate(
                label,
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=(
                    COLORS["muted"]
                    if math.isnan(value)
                    else COLORS["ink"]
                ),
                fontweight=(
                    "normal"
                    if math.isnan(value)
                    else "semibold"
                ),
            )

    return save_chart(fig, output_path)


def latest_platform_metrics(platform_rows: dict[str, list[dict]]) -> list[dict]:
    metrics = []
    for platform, rows in platform_rows.items():
        if not rows:
            continue
        latest = rows[-1]
        metrics.append(
            {
                "platform": platform,
                "label": platform.title(),
                "audience": number(latest.get("audience_total")),
                "net_growth": number(latest.get("net_growth")),
                "engagement_rate": number(latest.get("engagement_rate")),
                "total_engagement": number(latest.get("total_engagement")),
            }
        )
    return metrics


def render_platform_audience_growth_chart(
    platform_rows: dict[str, list[dict]],
    client: dict,
    period: dict,
    output_path: Path,
):
    metrics = latest_platform_metrics(platform_rows)
    fig, (audience_axis, growth_axis) = plt.subplots(
        1,
        2,
        figsize=(10, 5.625),
        facecolor="white",
        sharey=True,
        gridspec_kw={"width_ratios": (1.2, 1)},
    )
    fig.suptitle(
        "Cross-Platform Audience & Net Growth",
        x=0.07,
        y=0.95,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=COLORS["ink"],
    )
    fig.text(
        0.07,
        0.89,
        f"{client['client_name']} | {period['period_label']}",
        color=COLORS["muted"],
        fontsize=10,
    )

    positions = list(reversed(range(len(metrics))))
    labels = [metric["label"] for metric in metrics]
    audience_axis.set_title("Current Followers / Subscribers", loc="left", fontsize=11)
    growth_axis.set_title("Net Growth", loc="left", fontsize=11)
    for axis in (audience_axis, growth_axis):
        style_axis(axis)
        axis.grid(False)
        axis.grid(axis="x", color=COLORS["grid"], linewidth=0.8, alpha=0.8)
        axis.set_axisbelow(True)
    audience_axis.set_yticks(positions, labels)
    audience_axis.tick_params(axis="y", pad=8)
    growth_axis.tick_params(axis="y", left=False, labelleft=False)

    valid_audience = [
        metric["audience"]
        for metric in metrics
        if not math.isnan(metric["audience"]) and metric["audience"] > 0
    ]
    if valid_audience:
        maximum_audience = max(valid_audience)
        audience_axis.set_xscale("log")
        audience_axis.set_xlim(1, maximum_audience * 2.2)
        audience_axis.xaxis.set_major_formatter(FuncFormatter(compact_number))
        for position, metric in zip(positions, metrics):
            value = metric["audience"]
            if math.isnan(value) or value <= 0:
                audience_axis.text(
                    1.2,
                    position,
                    "N/A",
                    va="center",
                    color=COLORS["muted"],
                    fontsize=9,
                )
                continue
            color = PLATFORM_COLORS[metric["platform"]]
            audience_axis.hlines(
                position,
                1,
                value,
                color=color,
                linewidth=3,
                alpha=0.75,
            )
            audience_axis.scatter(
                value,
                position,
                s=115,
                color=color,
                edgecolor="white",
                linewidth=1.4,
                zorder=3,
            )
            audience_axis.annotate(
                compact_number(value),
                (value, position),
                xytext=(8, 0),
                textcoords="offset points",
                va="center",
                fontsize=8.5,
                color=COLORS["ink"],
            )
    else:
        no_data(audience_axis)

    valid_growth = [
        metric["net_growth"]
        for metric in metrics
        if not math.isnan(metric["net_growth"])
    ]
    if valid_growth:
        growth_extent = max(max(abs(value) for value in valid_growth) * 1.35, 1)
        growth_axis.set_xlim(-growth_extent, growth_extent)
        growth_axis.axvline(0, color=COLORS["ink"], linewidth=1.1)
        growth_axis.xaxis.set_major_formatter(FuncFormatter(compact_number))
        for position, metric in zip(positions, metrics):
            value = metric["net_growth"]
            if math.isnan(value):
                growth_axis.text(
                    0,
                    position,
                    "N/A",
                    ha="center",
                    va="center",
                    color=COLORS["muted"],
                    fontsize=9,
                )
                continue
            color = PLATFORM_COLORS[metric["platform"]]
            growth_axis.barh(
                position,
                value,
                height=0.42,
                color=color,
                alpha=0.9,
            )
            growth_axis.annotate(
                f"{value:+,.0f}",
                (value, position),
                xytext=(6 if value >= 0 else -6, 0),
                textcoords="offset points",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=8.5,
                color=COLORS["ink"],
            )
    else:
        no_data(growth_axis)

    fig.subplots_adjust(
        left=0.17,
        right=0.95,
        bottom=0.14,
        top=0.76,
        wspace=0.20,
    )
    return save_chart(fig, output_path)


def render_platform_engagement_scatter(
    platform_rows: dict[str, list[dict]],
    client: dict,
    period: dict,
    output_path: Path,
):
    metrics = latest_platform_metrics(platform_rows)
    plotted = [
        metric
        for metric in metrics
        if not math.isnan(metric["audience"])
        and metric["audience"] > 0
        and not math.isnan(metric["engagement_rate"])
    ]
    missing = [
        metric["label"]
        for metric in metrics
        if math.isnan(metric["audience"])
        or metric["audience"] <= 0
        or math.isnan(metric["engagement_rate"])
    ]
    fig, axis = create_chart_figure(
        "Engagement Rate vs Audience Size",
        (
            f"{client['client_name']} | {period['period_label']} | "
            "Bubble size represents total engagement"
        ),
    )
    style_axis(axis)
    axis.set_xlabel(
        "Current Followers / Subscribers (log scale)",
        color=COLORS["muted"],
        labelpad=10,
    )
    axis.set_ylabel(
        "Engagement Rate (%)",
        color=COLORS["muted"],
        labelpad=10,
    )

    if plotted:
        engagement_values = [
            max(metric["total_engagement"], 0)
            if not math.isnan(metric["total_engagement"])
            else 0
            for metric in plotted
        ]
        transformed = [math.log1p(value) for value in engagement_values]
        minimum, maximum = min(transformed), max(transformed)
        sizes = [
            420
            if maximum == minimum
            else 240 + ((value - minimum) / (maximum - minimum) * 620)
            for value in transformed
        ]
        legend_handles = []
        offsets = ((8, 8), (8, -17), (-8, 8), (-8, -17))
        for index, (metric, size) in enumerate(zip(plotted, sizes)):
            color = PLATFORM_COLORS[metric["platform"]]
            axis.scatter(
                metric["audience"],
                metric["engagement_rate"],
                s=size,
                color=color,
                edgecolor="white",
                linewidth=1.6,
                zorder=3,
            )
            x_offset, y_offset = offsets[index % len(offsets)]
            axis.annotate(
                metric["label"],
                (metric["audience"], metric["engagement_rate"]),
                xytext=(x_offset, y_offset),
                textcoords="offset points",
                ha="left" if x_offset > 0 else "right",
                va="bottom" if y_offset > 0 else "top",
                fontsize=8.5,
                color=COLORS["ink"],
                bbox={
                    "boxstyle": "round,pad=0.18",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.88,
                },
            )
            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="none",
                    markerfacecolor=color,
                    markeredgecolor="white",
                    markersize=9,
                    label=metric["label"],
                )
            )
        axis.set_xscale("log")
        audience_values = [metric["audience"] for metric in plotted]
        axis.set_xlim(min(audience_values) / 2, max(audience_values) * 2)
        axis.xaxis.set_major_formatter(FuncFormatter(compact_number))
        maximum_rate = max(metric["engagement_rate"] for metric in plotted)
        axis.set_ylim(0, max(maximum_rate * 1.35, 1))
        axis.legend(
            handles=legend_handles,
            frameon=False,
            loc="lower left",
            bbox_to_anchor=(0, 1.03),
            borderaxespad=0,
            fontsize=8.5,
            ncol=min(len(legend_handles), 4),
        )
    else:
        no_data(axis, "Audience dan engagement rate belum tersedia")

    if missing:
        fig.text(
            0.94,
            0.035,
            f"Not plotted (missing audience/ER): {', '.join(missing)}",
            ha="right",
            color=COLORS["muted"],
            fontsize=7.5,
        )
    return save_chart(fig, output_path)


def bubble_sizes(points: list[dict]) -> list[float]:
    followers = [
        max(number(point.get("followers")), 0)
        for point in points
    ]
    valid = [value for value in followers if not math.isnan(value)]
    if not valid:
        return [280 for _ in points]
    transformed = [math.log1p(value) for value in valid]
    minimum, maximum = min(transformed), max(transformed)
    sizes = []
    for value in followers:
        if math.isnan(value):
            sizes.append(220)
        elif maximum == minimum:
            sizes.append(420)
        else:
            ratio = (math.log1p(value) - minimum) / (maximum - minimum)
            sizes.append(220 + (ratio * 620))
    return sizes


def render_competitor_quadrant_chart(
    rows: list[dict],
    competitor_rows: list[dict],
    client: dict,
    period: dict,
    platform: str,
    output_path: Path,
):
    config = PLATFORMS[platform]
    latest = rows[-1] if rows else {}
    points = [
        {
            "name": str(client["client_code"]).upper(),
            "followers": latest.get("audience_total"),
            "growth": latest.get("audience_growth_rate"),
            "engagement_rate": latest.get("engagement_rate"),
            "is_client": True,
        }
    ]
    points.extend(
        {
            "name": row.get("profile_name") or "Competitor",
            "followers": row.get("total_followers"),
            "growth": row.get("follower_growth_rate"),
            "engagement_rate": row.get("engagement_rate"),
            "is_client": False,
        }
        for row in competitor_rows
    )
    plotted = [
        {
            **point,
            "growth": number(point["growth"]),
            "engagement_rate": number(point["engagement_rate"]),
        }
        for point in points
        if not math.isnan(number(point["growth"]))
        and not math.isnan(number(point["engagement_rate"]))
    ]
    missing = [
        point["name"]
        for point in points
        if math.isnan(number(point["growth"]))
        or math.isnan(number(point["engagement_rate"]))
    ]

    subtitle = (
        f"{client['client_name']} | {period['period_label']} | "
        f"Bubble size represents total {config['audience'].lower()}"
    )
    fig, axis = create_chart_figure(
        f"{platform.title()} Competitor Quadrant",
        subtitle,
    )
    style_axis(axis)
    axis.axvline(0, color=COLORS["ink"], linewidth=1.1, zorder=2)
    axis.axhline(0, color=COLORS["ink"], linewidth=1.1, zorder=2)
    axis.set_xlabel(
        f"{config['audience'][:-1] if config['audience'].endswith('s') else config['audience']} Growth (%)",
        color=COLORS["muted"],
        labelpad=10,
    )
    axis.set_ylabel(
        "Average Engagement Rate (%)",
        color=COLORS["muted"],
        labelpad=10,
    )

    if plotted:
        x_values = [point["growth"] for point in plotted]
        y_values = [point["engagement_rate"] for point in plotted]
        x_extent = max(max(abs(value) for value in x_values) * 1.35, 0.5)
        y_extent = max(max(abs(value) for value in y_values) * 1.35, 0.5)
        axis.set_xlim(-x_extent, x_extent)
        axis.set_ylim(-y_extent, y_extent)

        axis.axvspan(0, x_extent, ymin=0.5, ymax=1, color="#2A8C82", alpha=0.045)
        axis.axvspan(-x_extent, 0, ymin=0.5, ymax=1, color="#356D9A", alpha=0.035)
        axis.axvspan(-x_extent, 0, ymin=0, ymax=0.5, color="#C45A55", alpha=0.035)
        axis.axvspan(0, x_extent, ymin=0, ymax=0.5, color="#C9962E", alpha=0.03)

        axis.text(
            0.985,
            0.965,
            "Growth + | ER +",
            transform=axis.transAxes,
            ha="right",
            va="top",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.015,
            0.965,
            "Growth - | ER +",
            transform=axis.transAxes,
            ha="left",
            va="top",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.015,
            0.035,
            "Growth - | ER -",
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.985,
            0.035,
            "Growth + | ER -",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            color=COLORS["muted"],
            fontsize=8,
        )

        sizes = bubble_sizes(plotted)
        offsets = ((8, 9), (8, -16), (-8, 9), (-8, -16))
        legend_handles = []
        competitor_color_index = 1
        for index, (point, size) in enumerate(zip(plotted, sizes)):
            is_client = point["is_client"]
            if is_client:
                point_color = QUADRANT_COLORS[0]
            else:
                point_color = QUADRANT_COLORS[
                    competitor_color_index % len(QUADRANT_COLORS)
                ]
                competitor_color_index += 1
            axis.scatter(
                point["growth"],
                point["engagement_rate"],
                s=size,
                color=point_color,
                edgecolor="white",
                linewidth=1.6,
                alpha=0.95,
                zorder=4,
            )
            display_name = str(point["name"])
            if len(display_name) > 24:
                display_name = f"{display_name[:21]}..."
            x_offset, y_offset = offsets[index % len(offsets)]
            axis.annotate(
                display_name,
                (point["growth"], point["engagement_rate"]),
                xytext=(x_offset, y_offset),
                textcoords="offset points",
                ha="left" if x_offset > 0 else "right",
                va="bottom" if y_offset > 0 else "top",
                fontsize=8,
                color=COLORS["ink"],
                bbox={
                    "boxstyle": "round,pad=0.18",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.88,
                },
                zorder=5,
            )
            legend_name = str(point["name"])
            if len(legend_name) > 28:
                legend_name = f"{legend_name[:25]}..."
            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="none",
                    markerfacecolor=point_color,
                    markeredgecolor="white",
                    markersize=9,
                    label=legend_name,
                )
            )
        axis.legend(
            handles=legend_handles,
            frameon=False,
            loc="lower left",
            bbox_to_anchor=(0, 1.03),
            borderaxespad=0,
            fontsize=8.5,
            ncol=2,
            columnspacing=1.5,
            handletextpad=0.5,
        )
    else:
        axis.set_xlim(-1, 1)
        axis.set_ylim(-1, 1)
        axis.text(
            0.5,
            0.56,
            "Growth dan engagement rate belum tersedia",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color=COLORS["muted"],
            fontsize=11,
        )

    if missing:
        fig.text(
            0.94,
            0.035,
            f"Not plotted (missing Growth/ER): {', '.join(missing)}",
            ha="right",
            color=COLORS["muted"],
            fontsize=7.5,
        )
    return save_chart(fig, output_path)


def main():
    args = parse_args()
    if not 1 <= args.months <= 12:
        raise ValueError("--months must be between 1 and 12.")
    if args.month and not re.fullmatch(r"\d{4}-\d{2}", args.month):
        raise ValueError("--month must use YYYY-MM format, e.g. 2026-07.")

    engine = create_db_engine()
    client, period = fetch_context(engine, args.client_code, args.month)
    platforms = (
        connected_platforms(client) if args.platform == "all" else [args.platform]
    )
    if not platforms:
        raise ValueError("The selected client has no connected platforms.")

    output_files = []
    figures = []
    platform_rows = {}
    period_key = period["period_start"].strftime("%Y-%m")
    for platform in platforms:
        rows = fetch_trends(
            engine,
            str(client["id"]),
            period["period_start"],
            platform,
            args.months,
        )
        platform_rows[platform] = rows
        output_dir = (
            args.output_dir / slug(client["client_code"]) / period_key / platform
        )
        chart_specs = (
            (
                render_audience_and_growth_chart,
                output_dir / "audience_and_growth.png",
            ),
            (
                render_impressions_reach_chart,
                output_dir / "impressions_and_reach.png",
            ),
            (
                render_engagement_breakdown_chart,
                output_dir / "engagement_breakdown.png",
            ),
        )
        for render_chart, output_path in chart_specs:
            figure = render_chart(
                rows,
                client["client_name"],
                platform,
                output_path,
            )
            if args.show:
                figures.append(figure)
            else:
                plt.close(figure)
            output_files.append(output_path)
        competitor_rows = fetch_competitor_rows(
            engine,
            client,
            period,
            platform,
        )
        quadrant_path = output_dir / "competitor_quadrant.png"
        figure = render_competitor_quadrant_chart(
            rows,
            competitor_rows,
            client,
            period,
            platform,
            quadrant_path,
        )
        if args.show:
            figures.append(figure)
        else:
            plt.close(figure)
        output_files.append(quadrant_path)

    if len(platform_rows) >= 2:
        overview_dir = (
            args.output_dir
            / slug(client["client_code"])
            / period_key
            / "performance_overview"
        )
        overview_specs = (
            (
                render_platform_audience_growth_chart,
                overview_dir / "performance_audience_growth.png",
            ),
            (
                render_platform_engagement_scatter,
                overview_dir / "performance_engagement_vs_followers.png",
            ),
        )
        for render_chart, output_path in overview_specs:
            figure = render_chart(
                platform_rows,
                client,
                period,
                output_path,
            )
            if args.show:
                figures.append(figure)
            else:
                plt.close(figure)
            output_files.append(output_path)

    print("Generated chart previews:")
    for output_file in output_files:
        print(f"- {output_file.resolve()}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
