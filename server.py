import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

mcp = FastMCP("App Usage Agent")

BASE_URL = os.getenv("ACTIVITYWATCH_BASE_URL", "http://localhost:5600/api/0")


@mcp.custom_route("/", methods=["GET"])
async def root_info(_: Request) -> Response:
    return JSONResponse(
        {
            "name": "App Usage Agent",
            "status": "ok",
            "mcp_endpoint": "/mcp",
            "note": "Use an MCP client to call tools. This root path is only for health/info.",
        }
    )


@mcp.custom_route("/favicon.ico", methods=["GET"])
async def favicon(_: Request) -> Response:
    return Response(status_code=204)


@mcp.tool()
def get_app_usage():
    """
    Get app usage summary from ActivityWatch
    """

    return _build_usage_minutes(days=1)


def _fetch_buckets():
    buckets_resp = requests.get(f"{BASE_URL}/buckets", timeout=10)
    buckets_resp.raise_for_status()
    return buckets_resp.json()


def _find_window_bucket_key(buckets: dict) -> str | None:
    for key in buckets.keys():
        if "window" in key:
            return key
    return None


def _fetch_events(bucket_key: str) -> list[dict]:
    events_resp = requests.get(f"{BASE_URL}/buckets/{bucket_key}/events", timeout=15)
    events_resp.raise_for_status()
    return events_resp.json()


def _parse_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _aggregate_usage_seconds(
    events: list[dict], start: datetime | None = None, end: datetime | None = None
) -> dict[str, float]:
    usage = defaultdict(float)

    for event in events:
        event_start = _parse_timestamp(event.get("timestamp"))
        if start and event_start and event_start < start:
            continue
        if end and event_start and event_start > end:
            continue

        app = event.get("data", {}).get("app", "Unknown")
        duration = float(event.get("duration", 0) or 0)
        usage[app] += duration

    return dict(usage)


def _build_usage_minutes(days: int = 1) -> dict[str, float] | str:
    if days < 1:
        return "days must be >= 1"

    try:
        buckets = _fetch_buckets()
        bucket_key = _find_window_bucket_key(buckets)
        if not bucket_key:
            return "No app usage bucket found"

        events = _fetch_events(bucket_key)
    except requests.RequestException as exc:
        return f"Failed to fetch ActivityWatch data: {exc}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    usage_seconds = _aggregate_usage_seconds(events, start=start, end=end)

    return {
        app: round(seconds / 60, 2)
        for app, seconds in usage_seconds.items()
        if seconds > 0
    }


def _build_suggestions(usage_minutes: dict[str, float]) -> list[str]:
    if not usage_minutes:
        return ["No usage data detected in this period."]

    total_minutes = sum(usage_minutes.values())
    sorted_apps = sorted(usage_minutes.items(), key=lambda item: item[1], reverse=True)
    top_app, top_minutes = sorted_apps[0]
    top_share = (top_minutes / total_minutes) * 100 if total_minutes else 0

    browser_minutes = sum(
        minutes
        for app, minutes in usage_minutes.items()
        if any(
            keyword in app.lower()
            for keyword in ["chrome", "safari", "edge", "firefox", "browser"]
        )
    )
    chat_minutes = sum(
        minutes
        for app, minutes in usage_minutes.items()
        if any(
            keyword in app.lower()
            for keyword in ["wechat", "slack", "discord", "telegram", "line", "message"]
        )
    )

    suggestions = []
    if top_share >= 40:
        suggestions.append(
            f"Top app '{top_app}' takes {top_share:.1f}% of your time. Consider setting a daily cap or break timer."
        )

    if browser_minutes >= 180:
        suggestions.append(
            "Browser usage is high (>3h). Try separating focused work tabs from entertainment tabs."
        )

    if chat_minutes >= 90:
        suggestions.append(
            "Messaging usage is high (>1.5h). Batch notifications into fixed check-in windows."
        )

    if total_minutes >= 360:
        suggestions.append(
            "You used apps for over 6 hours. Add 5-10 minute breaks every 60-90 minutes to reduce fatigue."
        )

    if not suggestions:
        suggestions.append(
            "Usage distribution looks balanced. Keep monitoring and protect your focus blocks."
        )

    return suggestions


@mcp.tool()
def get_app_usage_report(days: int = 1, top_n: int = 10):
    """
    Build a summarized usage report for the last N days with practical suggestions.
    """

    if days < 1 or days > 30:
        return "days must be between 1 and 30"
    if top_n < 1 or top_n > 50:
        return "top_n must be between 1 and 50"

    usage_minutes = _build_usage_minutes(days=days)
    if isinstance(usage_minutes, str):
        return usage_minutes

    total_minutes = round(sum(usage_minutes.values()), 2)
    top_apps = sorted(usage_minutes.items(), key=lambda item: item[1], reverse=True)[
        :top_n
    ]

    return {
        "period_days": days,
        "total_hours": round(total_minutes / 60, 2),
        "top_apps": [
            {"app": app, "minutes": round(minutes, 2)} for app, minutes in top_apps
        ],
        "suggestions": _build_suggestions(usage_minutes),
    }


@mcp.tool()
def get_daily_usage_trend(days: int = 7, top_n: int = 5):
    """
    Return daily usage trends and top apps per day for recent days.
    """

    if days < 1 or days > 30:
        return "days must be between 1 and 30"
    if top_n < 1 or top_n > 20:
        return "top_n must be between 1 and 20"

    try:
        buckets = _fetch_buckets()
        bucket_key = _find_window_bucket_key(buckets)
        if not bucket_key:
            return "No app usage bucket found"
        events = _fetch_events(bucket_key)
    except requests.RequestException as exc:
        return f"Failed to fetch ActivityWatch data: {exc}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    day_map: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for event in events:
        event_start = _parse_timestamp(event.get("timestamp"))
        if not event_start or event_start < start or event_start > end:
            continue

        day_key = event_start.date().isoformat()
        app = event.get("data", {}).get("app", "Unknown")
        duration = float(event.get("duration", 0) or 0)
        day_map[day_key][app] += duration

    trend = []
    for day_key in sorted(day_map.keys()):
        usage_seconds = day_map[day_key]
        total_minutes = sum(usage_seconds.values()) / 60
        top_apps = sorted(
            usage_seconds.items(), key=lambda item: item[1], reverse=True
        )[:top_n]
        trend.append(
            {
                "date": day_key,
                "total_hours": round(total_minutes / 60, 2),
                "top_apps": [
                    {"app": app, "minutes": round(seconds / 60, 2)}
                    for app, seconds in top_apps
                ],
            }
        )

    return {
        "period_days": days,
        "days_with_data": len(trend),
        "trend": trend,
    }


def _choose_transport(transport_arg: str) -> str:
    if transport_arg != "auto":
        return transport_arg

    # In an interactive terminal, stdio can receive blank lines from manual input.
    # Use HTTP transport for manual debugging and stdio for MCP clients (non-interactive).
    if sys.stdin.isatty() and sys.stdout.isatty():
        return "streamable-http"

    return "stdio"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="App Usage MCP server")
    parser.add_argument(
        "--transport",
        choices=["auto", "stdio", "sse", "streamable-http"],
        default="auto",
        help="Server transport. 'auto' chooses streamable-http for terminal use and stdio for MCP clients.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP host for sse/streamable-http transports",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port for sse/streamable-http transports",
    )
    args = parser.parse_args()

    chosen_transport = _choose_transport(args.transport)

    if chosen_transport in {"sse", "streamable-http"}:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(
            f"Starting MCP server with transport={chosen_transport} on http://{args.host}:{args.port}"
        )
    elif args.transport == "stdio" and sys.stdin.isatty():
        print(
            "Warning: stdio transport expects an MCP client. Avoid typing in this terminal.",
            file=sys.stderr,
        )

    mcp.run(transport=chosen_transport)
