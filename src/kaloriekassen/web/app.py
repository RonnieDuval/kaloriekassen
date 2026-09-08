"""FastAPI application serving the Kaloriekassen dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from kaloriekassen.web.repository import (
    database_is_available,
    get_dashboard,
    get_day,
)


WEB_ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="Kaloriekassen",
    description="Privat read-only sundheds- og energidashboard",
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=WEB_ROOT / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"default_days": 30},
    )


@app.get("/api/dashboard")
def dashboard_data(days: int = Query(default=30, ge=7, le=730)) -> dict:
    return get_dashboard(days)


@app.get("/api/days/{day}")
def day_data(day: date) -> dict:
    result = get_day(day.isoformat())
    if result is None:
        raise HTTPException(status_code=404, detail="Ingen data for den valgte dag")
    return result


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    if not database_is_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
