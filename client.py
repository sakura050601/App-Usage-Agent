import argparse
from typing import Any

import anyio

from insight_engine import build_deep_insights
from mcp_service import MCPServiceError, fetch_dashboard_data


def _format_report(report: dict[str, Any]) -> str:
    lines = []
    lines.append("=== App Usage Report ===")
    lines.append(f"Period: last {report.get('period_days', '?')} day(s)")
    lines.append(f"Total: {report.get('total_hours', 0)} hour(s)")
    lines.append("")
    lines.append("Top Apps:")

    top_apps = report.get("top_apps", [])
    if not top_apps:
        lines.append("- No app data")
    else:
        for idx, item in enumerate(top_apps, start=1):
            app = item.get("app", "Unknown")
            minutes = item.get("minutes", 0)
            lines.append(f"{idx}. {app}: {minutes} min")

    lines.append("")
    lines.append("Suggestions:")
    suggestions = report.get("suggestions", [])
    if not suggestions:
        lines.append("- No suggestions")
    else:
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")

    return "\n".join(lines)


def _format_trend(trend: dict[str, Any]) -> str:
    lines = []
    lines.append("=== Daily Trend ===")
    lines.append(f"Days requested: {trend.get('period_days', '?')}")
    lines.append(f"Days with data: {trend.get('days_with_data', 0)}")

    for day in trend.get("trend", []):
        lines.append("")
        lines.append(
            f"{day.get('date', 'unknown-date')} | {day.get('total_hours', 0)} hour(s)"
        )
        top_apps = day.get("top_apps", [])
        if not top_apps:
            lines.append("- No app data")
            continue

        for item in top_apps:
            app = item.get("app", "Unknown")
            minutes = item.get("minutes", 0)
            lines.append(f"- {app}: {minutes} min")

    return "\n".join(lines)


def _format_insights(insights: dict[str, Any]) -> str:
    focus = insights.get("focus_score", {})
    components = focus.get("components", {})
    narrative = insights.get("deep_narrative", "")
    actions = insights.get("deep_actions", [])

    lines = []
    lines.append("=== Deep Insights ===")
    lines.append(f"Focus Score: {focus.get('score', '--')}")
    lines.append(f"Source: {insights.get('analysis_source', 'rules')}")
    lines.append("")
    if narrative:
        lines.append("Narrative:")
        lines.append(narrative)
        lines.append("")
    lines.append("Components:")
    for name, value in components.items():
        lines.append(f"- {name}: {value}")

    lines.append("")
    lines.append("Action Plan:")
    for action in actions:
        lines.append(f"- {action}")

    return "\n".join(lines)


async def _run(
    endpoint: str,
    report_days: int,
    report_top_n: int,
    trend_days: int,
    trend_top_n: int,
) -> None:
    try:
        data = await fetch_dashboard_data(
            endpoint=endpoint,
            report_days=report_days,
            report_top_n=report_top_n,
            trend_days=trend_days,
            trend_top_n=trend_top_n,
        )
    except MCPServiceError as exc:
        print(f"Error: {exc}")
        return

    report_payload = data.get("report", {})
    trend_payload = data.get("trend", {})

    if not isinstance(report_payload, dict) or not isinstance(trend_payload, dict):
        print("Unexpected payload.")
        print("report:", report_payload)
        print("trend:", trend_payload)
        return

    print("Connected. Tools:", ", ".join(data.get("tools", [])))
    print("")
    print(_format_report(report_payload))
    print("")
    print(_format_trend(trend_payload))
    print("")

    insights = await build_deep_insights(report_payload, trend_payload)
    print(_format_insights(insights))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Readable MCP client for app usage analysis"
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/mcp",
        help="MCP streamable-http endpoint",
    )
    parser.add_argument(
        "--report-days", type=int, default=1, help="Days for get_app_usage_report"
    )
    parser.add_argument(
        "--report-top-n", type=int, default=10, help="Top N apps in report"
    )
    parser.add_argument(
        "--trend-days", type=int, default=7, help="Days for get_daily_usage_trend"
    )
    parser.add_argument(
        "--trend-top-n", type=int, default=5, help="Top N apps per day in trend"
    )
    args = parser.parse_args()

    anyio.run(
        _run,
        args.endpoint,
        args.report_days,
        args.report_top_n,
        args.trend_days,
        args.trend_top_n,
    )


if __name__ == "__main__":
    main()
