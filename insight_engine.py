import os
import json
from typing import Any

import httpx


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _calculate_top_share(report: dict[str, Any]) -> tuple[str, float, float]:
    total_hours = _safe_number(report.get("total_hours"))
    top_apps = report.get("top_apps", [])
    if total_hours <= 0 or not top_apps:
        return "Unknown", 0.0, 0.0

    top_app = top_apps[0].get("app", "Unknown")
    top_minutes = _safe_number(top_apps[0].get("minutes"))
    top_share = (top_minutes / (total_hours * 60)) * 100
    return top_app, top_minutes, top_share


def _calculate_trend_delta(trend: dict[str, Any]) -> tuple[float, float, float]:
    trend_rows = trend.get("trend", [])
    if len(trend_rows) < 2:
        return 0.0, 0.0, 0.0

    first = _safe_number(trend_rows[0].get("total_hours"))
    last = _safe_number(trend_rows[-1].get("total_hours"))
    delta_hours = last - first
    delta_percent = ((delta_hours / first) * 100) if first > 0 else 0.0
    avg_hours = sum(_safe_number(row.get("total_hours")) for row in trend_rows) / len(
        trend_rows
    )
    return delta_hours, delta_percent, avg_hours


def calculate_focus_score(
    report: dict[str, Any], trend: dict[str, Any]
) -> dict[str, Any]:
    total_hours = _safe_number(report.get("total_hours"))
    top_apps = report.get("top_apps", [])
    top_share = 0.0

    if total_hours > 0 and top_apps:
        top_minutes = _safe_number(top_apps[0].get("minutes"))
        top_share = (top_minutes / (total_hours * 60)) * 100

    consistency = 70.0
    trend_rows = trend.get("trend", [])
    if len(trend_rows) >= 2:
        totals = [_safe_number(row.get("total_hours")) for row in trend_rows]
        avg = sum(totals) / len(totals) if totals else 0.0
        volatility = 0.0
        if avg > 0:
            volatility = (max(totals) - min(totals)) / avg
        consistency = max(35.0, min(95.0, 90.0 - volatility * 35.0))

    efficiency = 80.0 if top_share >= 60 else 68.0
    balance = max(30.0, min(95.0, 100.0 - abs(55.0 - top_share) * 1.4))
    sustainability = 85.0 if 1.0 <= total_hours <= 8.0 else 65.0

    score = round(
        0.35 * efficiency + 0.3 * balance + 0.2 * consistency + 0.15 * sustainability,
        1,
    )

    return {
        "score": score,
        "components": {
            "efficiency": round(efficiency, 1),
            "focus_balance": round(balance, 1),
            "consistency": round(consistency, 1),
            "sustainability": round(sustainability, 1),
        },
    }


def _rule_based_actions(
    report: dict[str, Any], trend: dict[str, Any], user_goal: str | None = None
) -> list[str]:
    actions = []
    total_hours = _safe_number(report.get("total_hours"))
    top_apps = report.get("top_apps", [])

    if top_apps:
        app = top_apps[0].get("app", "Unknown")
        minutes = _safe_number(top_apps[0].get("minutes"))
        share = (minutes / (total_hours * 60) * 100) if total_hours > 0 else 0
        if share >= 70:
            actions.append(
                f"{app} 占比 {share:.1f}% 偏高，建议按 50 分钟专注 + 10 分钟休息节奏运行。"
            )

    trend_rows = trend.get("trend", [])
    if len(trend_rows) >= 2:
        first = _safe_number(trend_rows[0].get("total_hours"))
        last = _safe_number(trend_rows[-1].get("total_hours"))
        if first > 0:
            delta = ((last - first) / first) * 100
            if delta < -20:
                actions.append(
                    "近几天总使用时长明显下降，建议先排查是否被碎片化事务干扰。"
                )
            elif delta > 25:
                actions.append(
                    "近几天时长上升较快，建议增加休息窗口，防止后段疲劳导致效率下滑。"
                )

    if total_hours >= 6:
        actions.append("今日总时长超过 6 小时，建议加入番茄钟并设置晚间硬停止时间。")

    if user_goal:
        actions.append(
            f"结合你的目标“{user_goal}”，明天优先保证一个 90 分钟的无打扰深度工作块。"
        )

    if not actions:
        actions.append(
            "当前使用结构总体稳定，建议保持晚间复盘并持续跟踪前 3 个高频应用。"
        )

    return actions


def _build_rule_based_narrative(
    report: dict[str, Any],
    trend: dict[str, Any],
    focus_score: dict[str, Any],
    user_goal: str | None = None,
) -> str:
    total_hours = _safe_number(report.get("total_hours"))
    top_app, top_minutes, top_share = _calculate_top_share(report)
    delta_hours, delta_percent, avg_hours = _calculate_trend_delta(trend)
    components = focus_score.get("components", {})
    score = focus_score.get("score", 0)

    trend_rows = trend.get("trend", [])
    days_with_data = len(trend_rows)
    first_day = trend_rows[0].get("date", "未知") if trend_rows else "未知"
    last_day = trend_rows[-1].get("date", "未知") if trend_rows else "未知"

    narrative = (
        f"最近 {days_with_data} 天的使用情况显示，你的总活跃时长为 {total_hours:.2f} 小时，"
        f"其中占比最高的应用是 {top_app}，累计 {top_minutes:.2f} 分钟，占总时长约 {top_share:.1f}% ，"
        f"说明当前注意力仍然明显集中在单一主任务上。若以时间趋势看，从 {first_day} 到 {last_day} 的总时长变化为 {delta_hours:+.2f} 小时，"
        f"相对变化 {delta_percent:+.1f}% ，日均使用时长约 {avg_hours:.2f} 小时，这意味着近期节奏并不完全稳定，"
        f"需要观察是否存在碎片化事务、会议、消息打断或临时需求挤占了原本连续工作的窗口。"
        f"当前 Focus Score 为 {score} 分，其中效率 {components.get('efficiency', '--')}、平衡度 {components.get('focus_balance', '--')}、"
        f"一致性 {components.get('consistency', '--')}、可持续性 {components.get('sustainability', '--')}，"
        f"这组数字表明你并不是完全低效，而是更像“高强度但波动明显”的状态：有时能保持深度推进，"
        f"但也容易在高频应用与主工作之间切换，导致整体连续性下降。如果 {user_goal or '你的目标'} 依然是提升深度工作质量，"
        f"建议把接下来的一天拆成至少 2 个明确的专注块，并把非核心应用集中到固定时段处理，这样可以降低 context switching 的成本。"
        f"综合来看，目前的使用结构不是“时间不够”，而是“时间分布和注意力切分方式还不够稳”，"
        f"因此真正的优化方向不是单纯减少使用，而是让 {top_app} 之外的干扰变得更有边界，让主任务获得更连续的 50-90 分钟窗口。"
    )

    return narrative


async def _llm_actions(
    report: dict[str, Any],
    trend: dict[str, Any],
    user_goal: str | None,
    focus_score: dict[str, Any],
) -> dict[str, Any] | None:
    endpoint = os.getenv("APP_USAGE_LLM_ENDPOINT", "").strip()
    api_key = os.getenv("APP_USAGE_LLM_API_KEY", "").strip()
    model = os.getenv("APP_USAGE_LLM_MODEL", "gpt-4o-mini").strip()

    if not endpoint or not api_key:
        return None

    prompt = (
        "你是生产力教练。请基于以下数据输出 JSON，包含两个字段："
        "deep_narrative 和 deep_actions。deep_narrative 必须是中文长文，超过 200 字，"
        "必须包含总时长、Top App 占比、趋势变化、Focus Score 分项等具体数字；"
        "deep_actions 必须是 3 到 5 条中文行动建议，每条一句，强调明天可执行。\n\n"
        f"user_goal: {user_goal or '无'}\n"
        f"focus_score: {focus_score}\n"
        f"report: {report}\n"
        f"trend: {trend}\n"
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You generate strict JSON with deep_narrative and deep_actions in Chinese.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:  # noqa: BLE001
        return None

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    narrative = str(parsed.get("deep_narrative", "")).strip()
    actions = parsed.get("deep_actions", [])
    if not narrative or not isinstance(actions, list) or not actions:
        return None

    return {
        "deep_narrative": narrative,
        "deep_actions": [str(item).strip() for item in actions if str(item).strip()][
            :5
        ],
    }


async def build_deep_insights(
    report: dict[str, Any],
    trend: dict[str, Any],
    user_goal: str | None = None,
) -> dict[str, Any]:
    focus_score = calculate_focus_score(report, trend)
    actions = _rule_based_actions(report, trend, user_goal)
    narrative = _build_rule_based_narrative(report, trend, focus_score, user_goal)

    llm_result = await _llm_actions(report, trend, user_goal, focus_score)
    source = "llm" if llm_result else "rules"

    if llm_result:
        narrative = llm_result.get("deep_narrative", narrative)
        actions = llm_result.get("deep_actions", actions)

    return {
        "focus_score": focus_score,
        "analysis_source": source,
        "deep_narrative": narrative,
        "deep_actions": actions,
    }
