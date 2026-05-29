from datetime import datetime
from typing import Any


def render_markdown(analysis: dict[str, Any]) -> str:
    report = analysis.get("report", {})
    trend = analysis.get("trend", {})
    insights = analysis.get("insights", {})

    lines: list[str] = []
    lines.append(f"# App Usage Report ({datetime.now().strftime('%Y-%m-%d')})")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total Hours: {report.get('total_hours', 0)}")
    lines.append(f"- Period Days: {report.get('period_days', 0)}")
    lines.append(f"- Focus Score: {insights.get('focus_score', {}).get('score', 0)}")
    lines.append("")

    lines.append("## Top Apps")
    for item in report.get("top_apps", []):
        lines.append(f"- {item.get('app', 'Unknown')}: {item.get('minutes', 0)} min")
    lines.append("")

    lines.append("## Trend")
    for row in trend.get("trend", []):
        lines.append(f"- {row.get('date', 'unknown')}: {row.get('total_hours', 0)} h")
    lines.append("")

    lines.append("## Deep Suggestions")
    narrative = insights.get("deep_narrative", "")
    if narrative:
        lines.append(narrative)
        lines.append("")
    for action in insights.get("deep_actions", []):
        lines.append(f"- {action}")

    return "\n".join(lines)


def render_html(analysis: dict[str, Any]) -> str:
    report = analysis.get("report", {})
    trend = analysis.get("trend", {})
    insights = analysis.get("insights", {})

    top_apps_html = "".join(
        [
            f"<li><strong>{item.get('app', 'Unknown')}</strong>: {item.get('minutes', 0)} min</li>"
            for item in report.get("top_apps", [])
        ]
    )

    trend_html = "".join(
        [
            f"<li>{row.get('date', 'unknown')}: {row.get('total_hours', 0)} h</li>"
            for row in trend.get("trend", [])
        ]
    )

    advice_html = "".join(
        [f"<li>{action}</li>" for action in insights.get("deep_actions", [])]
    )
    narrative_html = insights.get("deep_narrative", "")

    return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>App Usage Report</title>
  <style>
    body {{ font-family: 'Arial', sans-serif; background: #f5f7fa; margin: 0; padding: 24px; color: #1f2937; }}
    .wrap {{ max-width: 920px; margin: 0 auto; }}
    .card {{ background: #fff; border-radius: 14px; padding: 18px; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(0,0,0,.06); }}
    h1 {{ margin: 0 0 12px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>App Usage Report</h1>
    <div class=\"card\">
      <h2>Summary</h2>
      <p style="line-height:1.75; white-space:pre-wrap;">{narrative_html}</p>
      <p>Total Hours: {report.get('total_hours', 0)}</p>
      <p>Period Days: {report.get('period_days', 0)}</p>
      <p>Focus Score: {insights.get('focus_score', {}).get('score', 0)}</p>
    </div>
    <div class=\"card\">
      <h2>Top Apps</h2>
      <ul>{top_apps_html}</ul>
    </div>
    <div class=\"card\">
      <h2>Trend</h2>
      <ul>{trend_html}</ul>
    </div>
    <div class=\"card\">
      <h2>Deep Suggestions</h2>
      <ul>{advice_html}</ul>
    </div>
  </div>
</body>
</html>
""".strip()
