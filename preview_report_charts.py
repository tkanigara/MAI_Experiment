from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
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
    fig, axis = plt.subplots(figsize=(10, 5.625), facecolor="none")
    fig.patch.set_alpha(0)
    axis.set_facecolor("none")
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
    fig.patch.set_facecolor("none")
    fig.patch.set_alpha(0)
    for axis in fig.get_axes():
        axis.set_facecolor("none")
        axis.patch.set_alpha(0)
    fig.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
        transparent=True,
        facecolor="none",
        edgecolor="none",
    )
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
    axis.set_ylabel(
        f"Total {config['audience']}",
        color=COLORS["muted"],
        labelpad=10,
    )

    handles = []
    if available(totals):
        audience_values = [
            0 if math.isnan(value) else value
            for value in totals
        ]
        audience_bars = axis.bar(
            x_values,
            audience_values,
            width=0.58,
            color=PLATFORM_COLORS[platform],
            alpha=0.86,
            label=f"Total {config['audience']}",
            zorder=2,
        )
        valid_totals = [value for value in totals if not math.isnan(value)]
        maximum = max(valid_totals)
        axis.set_ylim(0, max(maximum * 1.2, 1))
        for index, bar in enumerate(audience_bars):
            value = totals[index]
            label = "N/A" if math.isnan(value) else compact_number(value)
            axis.annotate(
                label,
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 7),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=COLORS["ink"],
                fontweight="semibold",
            )
        handles.append(audience_bars)

    growth_axis = axis.twinx()
    growth_axis.spines["top"].set_visible(False)
    growth_axis.spines["left"].set_visible(False)
    growth_axis.spines["right"].set_color(COLORS["grid"])
    growth_axis.tick_params(colors=COLORS["muted"], labelsize=9)
    growth_axis.grid(False)
    growth_axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
    growth_axis.set_ylabel(
        "Net Growth",
        color=COLORS["muted"],
        labelpad=10,
    )
    positive_growth_color = "#0F6B5F"
    negative_growth_color = "#B42318"
    if available(net_growth):
        plotted_growth = [
            math.nan if math.isnan(value) else max(value, 0)
            for value in net_growth
        ]
        growth_line = growth_axis.plot(
            x_values,
            plotted_growth,
            color=positive_growth_color,
            linewidth=1.8,
            linestyle=(0, (4, 3)),
            label="Net Growth",
            zorder=4,
        )[0]
        valid_display_growth = [
            value for value in plotted_growth if not math.isnan(value)
        ]
        growth_axis.set_ylim(
            0,
            max(max(valid_display_growth, default=0) * 1.35, 1),
        )
        for index, value in enumerate(net_growth):
            if math.isnan(value):
                continue
            display_value = max(value, 0)
            dot_color = (
                positive_growth_color
                if value >= 0
                else negative_growth_color
            )
            growth_axis.scatter(
                index,
                display_value,
                s=125,
                color=dot_color,
                edgecolor="white",
                linewidth=1.5,
                zorder=5,
                clip_on=False,
            )
            value = net_growth[index]
            if value > 0:
                label = f"+{compact_number(value)}"
            else:
                label = compact_number(value)
            growth_axis.annotate(
                label,
                (index, display_value),
                xytext=(0, 9),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=dot_color,
                fontweight="semibold",
                path_effects=[
                    path_effects.withStroke(
                        linewidth=3,
                        foreground="white",
                    )
                ],
            )
        handles.append(growth_line)

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
        ("Likes", values(rows, "likes"), "#4F7FE5"),
        ("Comments", values(rows, "comments"), "#D84B3A"),
        ("Shares", values(rows, "shares"), "#F1B82D"),
        (
            "Total Engagement",
            values(rows, "total_engagement"),
            "#55A958",
        ),
    )
    fig, axis = create_chart_figure(
        f"{platform.title()} Engagement Breakdown",
        f"{subtitle} | Likes, comments, shares, and total engagement",
    )
    style_axis(axis)
    axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    axis.set_xticks(x_values, labels)
    axis.set_xlim(-0.5, len(rows) - 0.5)
    axis.set_ylabel("Engagement", color=COLORS["muted"], labelpad=10)

    if any(available(series) for _, series, _ in metric_specs):
        bottoms = [0.0 for _ in rows]
        handles = []
        normalized_series = []
        for metric_label, series, color in metric_specs:
            plot_values = [
                0 if math.isnan(value) else value
                for value in series
            ]
            normalized_series.append(plot_values)
            bars = axis.bar(
                x_values,
                plot_values,
                width=0.58,
                bottom=bottoms,
                color=color,
                alpha=0.88,
                label=metric_label,
                zorder=2,
            )
            handles.append(bars)
            bottoms = [
                bottom + value
                for bottom, value in zip(bottoms, plot_values)
            ]

        maximum = max(bottoms, default=0)
        axis.set_ylim(0, max(maximum * 1.28, 1))

        for month_index, stack_height in enumerate(bottoms):
            if stack_height <= 0:
                continue
            month_values = [
                series[month_index]
                for series in normalized_series
            ]
            if stack_height < maximum * 0.18:
                visible_indexes = [
                    index
                    for index, value in enumerate(month_values)
                    if value > 0
                ]
                outside_step = maximum * 0.055
                outside_start = stack_height + (maximum * 0.035)
                label_positions = {
                    metric_index: outside_start
                    + (position * outside_step)
                    for position, metric_index in enumerate(visible_indexes)
                }
            else:
                likes = month_values[0]
                upper_height = max(stack_height - likes, 0)
                label_positions = {
                    0: likes / 2,
                    1: likes + (upper_height * 0.20),
                    2: likes + (upper_height * 0.43),
                    3: likes + (upper_height * 0.72),
                }

            for metric_index, (metric_label, _, color) in enumerate(
                metric_specs
            ):
                value = month_values[metric_index]
                if value <= 0:
                    continue
                axis.annotate(
                    compact_number(value),
                    (month_index, label_positions[metric_index]),
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    color=color,
                    fontweight="semibold",
                    path_effects=[
                        path_effects.withStroke(
                            linewidth=3,
                            foreground="white",
                        )
                    ],
                    zorder=5,
                )

        legend_handles = list(reversed(handles))
        legend_labels = [
            metric_specs[index][0]
            for index in reversed(range(len(metric_specs)))
        ]
        legend = axis.legend(
            handles=legend_handles,
            labels=legend_labels,
            frameon=False,
            loc="lower left",
            bbox_to_anchor=(0, 1.03),
            borderaxespad=0,
            fontsize=8.5,
            ncol=4,
        )
        legend_colors = [
            metric_specs[index][2]
            for index in reversed(range(len(metric_specs)))
        ]
        for legend_text, color in zip(legend.get_texts(), legend_colors):
            legend_text.set_color(color)
    else:
        no_data(axis)

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
    fig, audience_axis = create_chart_figure(
        "Current Audience and Net Growth by Platform",
        (
            f"{client['client_name']} | {period['period_label']} | "
            "Audience uses a logarithmic scale"
        ),
    )
    growth_axis = audience_axis.twinx()
    style_axis(audience_axis)
    growth_axis.spines["top"].set_visible(False)
    growth_axis.spines["left"].set_visible(False)
    growth_axis.spines["right"].set_color(COLORS["grid"])
    growth_axis.tick_params(axis="y", colors=COLORS["muted"], labelsize=8.5)
    growth_axis.grid(False)

    positions = list(range(len(metrics)))
    labels = [metric["label"] for metric in metrics]
    audience_values = [
        metric["audience"]
        if not math.isnan(metric["audience"]) and metric["audience"] > 0
        else math.nan
        for metric in metrics
    ]
    bar_values = [
        max(value, 1) if not math.isnan(value) else 1
        for value in audience_values
    ]
    colors = [PLATFORM_COLORS[metric["platform"]] for metric in metrics]
    bars = audience_axis.bar(
        positions,
        [max(value - 1, 0.01) for value in bar_values],
        bottom=1,
        width=0.58,
        color=colors,
        alpha=0.88,
        zorder=2,
    )
    audience_axis.set_xticks(positions, labels)
    audience_axis.tick_params(axis="x", pad=8)
    audience_axis.set_ylabel(
        "Current Followers / Subscribers",
        color=COLORS["muted"],
        labelpad=10,
    )
    audience_axis.grid(
        axis="y",
        color=COLORS["grid"],
        linewidth=0.8,
        alpha=0.8,
    )
    audience_axis.set_axisbelow(True)

    valid_audience = [value for value in audience_values if not math.isnan(value)]
    if valid_audience:
        audience_axis.set_yscale("log")
        audience_axis.set_ylim(
            max(min(valid_audience) / 2.5, 1),
            max(valid_audience) * 2.1,
        )
        audience_axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
        for bar, value in zip(bars, audience_values):
            if math.isnan(value):
                audience_axis.annotate(
                    "N/A",
                    (bar.get_x() + bar.get_width() / 2, 1),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    color=COLORS["muted"],
                    fontsize=8.5,
                )
                continue
            audience_axis.annotate(
                compact_number(value),
                (bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 7),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=COLORS["ink"],
                fontweight="semibold",
            )
    else:
        no_data(audience_axis)

    valid_growth = [
        metric["net_growth"]
        for metric in metrics
        if not math.isnan(metric["net_growth"])
    ]
    positive_growth_color = "#0F6B5F"
    negative_growth_color = "#B42318"
    if valid_growth:
        plotted_growth = [max(value, 0) for value in valid_growth]
        growth_maximum = max(max(plotted_growth), 1)
        growth_axis.set_ylim(0, growth_maximum * 1.35)
        growth_axis.set_ylabel(
            "Net Growth",
            color=COLORS["muted"],
            labelpad=10,
        )
        growth_axis.yaxis.set_major_formatter(FuncFormatter(compact_number))
        for position, metric in zip(positions, metrics):
            value = metric["net_growth"]
            if math.isnan(value):
                growth_axis.annotate(
                    "N/A",
                    (position, 0),
                    xytext=(0, 9),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    color=COLORS["muted"],
                    fontsize=8,
                )
                continue
            display_value = max(value, 0)
            dot_color = (
                positive_growth_color
                if value >= 0
                else negative_growth_color
            )
            growth_axis.scatter(
                position,
                display_value,
                s=145,
                color=dot_color,
                edgecolor="white",
                linewidth=1.5,
                zorder=5,
                clip_on=False,
            )
            growth_axis.annotate(
                f"{value:+,.0f}",
                (position, display_value),
                xytext=(0, 9),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=dot_color,
                fontweight="semibold",
                path_effects=[
                    path_effects.withStroke(
                        linewidth=3,
                        foreground="white",
                    )
                ],
            )
    else:
        growth_axis.set_ylim(0, 1)
        growth_axis.set_yticks([])

    audience_legend = Line2D(
        [0],
        [0],
        marker="s",
        color="none",
        markerfacecolor=COLORS["blue"],
        markeredgecolor="none",
        markersize=9,
        label="Current audience (platform colors)",
    )
    growth_legend = Line2D(
        [0],
        [0],
        marker="o",
        color="none",
        markerfacecolor=positive_growth_color,
        markeredgecolor="white",
        markeredgewidth=1.2,
        markersize=9,
        label="Net growth (negative values plotted at zero)",
    )
    audience_axis.legend(
        handles=[audience_legend, growth_legend],
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(0, 1.03),
        borderaxespad=0,
        fontsize=8.5,
        ncol=2,
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
        "Cross-Platform Engagement vs Audience Quadrant",
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
        audience_values = [metric["audience"] for metric in plotted]
        engagement_rates = [metric["engagement_rate"] for metric in plotted]
        audience_midpoint = math.exp(
            sum(math.log(value) for value in audience_values)
            / len(audience_values)
        )
        engagement_midpoint = sum(engagement_rates) / len(engagement_rates)
        x_min = max(min(audience_values) / 2, 1)
        x_max = max(audience_values) * 2
        y_min = 0
        y_max = max(max(engagement_rates) * 1.4, engagement_midpoint * 1.6, 1)
        y_split = (engagement_midpoint - y_min) / (y_max - y_min)

        axis.set_xscale("log")
        axis.set_xlim(x_min, x_max)
        axis.set_ylim(y_min, y_max)
        axis.xaxis.set_major_formatter(FuncFormatter(compact_number))
        axis.axvline(
            audience_midpoint,
            color=COLORS["ink"],
            linewidth=1.1,
            zorder=2,
        )
        axis.axhline(
            engagement_midpoint,
            color=COLORS["ink"],
            linewidth=1.1,
            zorder=2,
        )
        axis.axvspan(
            audience_midpoint,
            x_max,
            ymin=y_split,
            ymax=1,
            color="#2A8C82",
            alpha=0.045,
        )
        axis.axvspan(
            x_min,
            audience_midpoint,
            ymin=y_split,
            ymax=1,
            color="#356D9A",
            alpha=0.035,
        )
        axis.axvspan(
            x_min,
            audience_midpoint,
            ymin=0,
            ymax=y_split,
            color="#C45A55",
            alpha=0.035,
        )
        axis.axvspan(
            audience_midpoint,
            x_max,
            ymin=0,
            ymax=y_split,
            color="#C9962E",
            alpha=0.03,
        )
        axis.text(
            0.985,
            0.965,
            "High Audience | High ER",
            transform=axis.transAxes,
            ha="right",
            va="top",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.015,
            0.965,
            "Low Audience | High ER",
            transform=axis.transAxes,
            ha="left",
            va="top",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.015,
            0.035,
            "Low Audience | Low ER",
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            color=COLORS["muted"],
            fontsize=8,
        )
        axis.text(
            0.985,
            0.035,
            "High Audience | Low ER",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            color=COLORS["muted"],
            fontsize=8,
        )

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
