"""
InterX BD Intelligence Platform — FastAPI Web Application
"""
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

from database import (
    get_dashboard_stats, get_notices, get_notice_detail,
    get_sites_list, update_notice_status, ingest_pipeline_result,
)

app = FastAPI(title="InterX BD Intelligence Platform", version="1.0.0")

BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


# ── Page Routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    stats = get_dashboard_stats()
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats})


@app.get("/notices", response_class=HTMLResponse)
async def page_notices(
    request: Request,
    grade: str = "",
    site: str = "",
    search: str = "",
    l3: bool = False,
    urgent: bool = False,
    status: str = "",
    sort: str = "priority_score",
    dir: str = "DESC",
    page: int = 1,
):
    result = get_notices(
        grade=grade, site=site, search=search,
        l3_only=l3, urgent_only=urgent, status=status,
        sort_by=sort, sort_dir=dir, page=page,
    )
    sites = get_sites_list()
    return templates.TemplateResponse(request, "notices.html", {
        "result": result,
        "sites": sites,
        "filters": {"grade": grade, "site": site, "search": search, "l3": l3,
                     "urgent": urgent, "status": status, "sort": sort, "dir": dir},
    })


@app.get("/notice/{notice_id}", response_class=HTMLResponse)
async def page_notice_detail(request: Request, notice_id: str):
    notice = get_notice_detail(notice_id)
    if not notice:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return templates.TemplateResponse(request, "notice_detail.html", {"notice": notice})


@app.get("/pipeline", response_class=HTMLResponse)
async def page_pipeline(request: Request):
    stats = get_dashboard_stats()
    return templates.TemplateResponse(request, "pipeline.html", {"runs": stats["recent_runs"]})


# ── API Routes (for Colab sync & AJAX) ──────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    return get_dashboard_stats()


@app.get("/api/notices")
async def api_notices(
    grade: str = "", site: str = "", search: str = "",
    l3: bool = False, urgent: bool = False, status: str = "",
    sort: str = "priority_score", dir: str = "DESC",
    page: int = 1, per_page: int = 30,
):
    return get_notices(
        grade=grade, site=site, search=search,
        l3_only=l3, urgent_only=urgent, status=status,
        sort_by=sort, sort_dir=dir, page=page, per_page=per_page,
    )


@app.get("/api/notice/{notice_id}")
async def api_notice(notice_id: str):
    n = get_notice_detail(notice_id)
    return n if n else JSONResponse({"error": "not found"}, 404)


@app.post("/api/notice/{notice_id}/update")
async def api_update_notice(notice_id: str, request: Request):
    body = await request.json()
    field = body.get("field", "")
    value = body.get("value", "")
    reason = body.get("reason", "")
    if field not in ("status", "bd_milestone", "memo"):
        return JSONResponse({"error": "invalid field"}, 400)
    update_notice_status(notice_id, field, value, reason)
    return {"ok": True}


@app.post("/api/pipeline/sync")
async def api_pipeline_sync(request: Request):
    """Receive pipeline results from Colab."""
    data = await request.json()
    count = ingest_pipeline_result(data)
    return {"ok": True, "ingested": count, "execution_id": data.get("execution_id", "")}


@app.get("/api/health")
async def api_health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
