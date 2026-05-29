import json
from datetime import datetime, timezone
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPServiceError(Exception):
    pass


def _extract_tool_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    text_blocks: list[str] = []
    for block in getattr(result, "content", []):
        if getattr(block, "type", None) == "text":
            text_blocks.append(getattr(block, "text", ""))

    if not text_blocks:
        return {"raw": str(result)}

    text = text_blocks[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


async def fetch_dashboard_data(
    endpoint: str,
    report_days: int = 1,
    report_top_n: int = 10,
    trend_days: int = 7,
    trend_top_n: int = 5,
) -> dict[str, Any]:
    try:
        async with streamable_http_client(endpoint) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_names = [tool.name for tool in tools_result.tools]

                report_result = await session.call_tool(
                    "get_app_usage_report",
                    {"days": report_days, "top_n": report_top_n},
                )
                trend_result = await session.call_tool(
                    "get_daily_usage_trend",
                    {"days": trend_days, "top_n": trend_top_n},
                )
    except Exception as exc:  # noqa: BLE001
        raise MCPServiceError(
            "Unable to reach MCP server. Make sure server.py is running and endpoint is correct."
        ) from exc

    report_payload = _extract_tool_payload(report_result)
    trend_payload = _extract_tool_payload(trend_result)

    return {
        "endpoint": endpoint,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "tools": tool_names,
        "report": report_payload,
        "trend": trend_payload,
    }
