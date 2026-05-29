from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from insight_engine import build_deep_insights
from mcp_service import MCPServiceError, fetch_dashboard_data
from report_export import render_html, render_markdown

app = FastAPI(title="App Usage Dashboard")
templates = Jinja2Templates(directory="templates")


class AnalyzeRequest(BaseModel):
    endpoint: str = Field(default="http://127.0.0.1:8000/mcp")
    report_days: int = Field(default=1, ge=1, le=30)
    report_top_n: int = Field(default=10, ge=1, le=50)
    trend_days: int = Field(default=7, ge=1, le=30)
    trend_top_n: int = Field(default=5, ge=1, le=20)
    user_goal: str | None = Field(default=None)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _build_analysis(payload: AnalyzeRequest) -> dict[str, Any]:
    try:
        data = await fetch_dashboard_data(
            endpoint=payload.endpoint,
            report_days=payload.report_days,
            report_top_n=payload.report_top_n,
            trend_days=payload.trend_days,
            trend_top_n=payload.trend_top_n,
        )
    except MCPServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    report = data.get("report", {})
    trend = data.get("trend", {})

    if isinstance(report, str):
        raise HTTPException(status_code=400, detail=report)
    if isinstance(trend, str):
        raise HTTPException(status_code=400, detail=trend)

    insights = await build_deep_insights(report, trend, payload.user_goal)

    return {
        "meta": {
            "endpoint": data.get("endpoint"),
            "fetched_at": data.get("fetched_at"),
            "tools": data.get("tools", []),
        },
        "report": report,
        "trend": trend,
        "insights": insights,
    }


@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
    return await _build_analysis(payload)


@app.post("/api/export/markdown")
async def export_markdown(payload: AnalyzeRequest) -> Response:
    analysis = await _build_analysis(payload)
    content = render_markdown(analysis)
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=app-usage-report.md"},
    )


@app.post("/api/export/html")
async def export_html(payload: AnalyzeRequest) -> Response:
    analysis = await _build_analysis(payload)
    content = render_html(analysis)
    return Response(
        content=content,
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=app-usage-report.html"},
    )
