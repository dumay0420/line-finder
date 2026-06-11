"""LINE@ 客戶探測器 — FastAPI 後端"""
import uuid
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from searcher import run_full_search
from exporter import build_excel

app = FastAPI(title="LINE@ 客戶探測器")

# 任務暫存（記憶體）
jobs: dict = {}


class SearchParams(BaseModel):
    industry: str
    counties: list[str]
    excludes: list[str] = []


@app.get("/")
async def index():
    html = Path("static/index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/search")
async def create_job(params: SearchParams):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "pending",
        "results": [],
        "params": params.model_dump(),
        "excel_path": None,
    }
    return {"job_id": job_id}


@app.websocket("/ws/{job_id}")
async def ws_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()

    job = jobs.get(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "找不到任務 ID"})
        await websocket.close()
        return

    job["status"] = "running"
    p = job["params"]

    try:
        async for event in run_full_search(
            industry=p["industry"],
            counties=p["counties"],
            excludes=p["excludes"],
        ):
            await websocket.send_json(event)

            if event.get("type") == "found":
                job["results"].append(event["data"])

            if event.get("type") == "complete":
                # 產生 Excel
                if job["results"]:
                    path = build_excel(job["results"], p["industry"], job_id)
                    job["excel_path"] = path
                    await websocket.send_json({
                        "type": "download_ready",
                        "url": f"/api/download/{job_id}",
                        "total": len(job["results"]),
                    })

        job["status"] = "done"

    except WebSocketDisconnect:
        job["status"] = "cancelled"
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        job["status"] = "error"


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("excel_path"):
        return {"error": "檔案不存在"}
    path = job["excel_path"]
    filename = Path(path).name
    return FileResponse(path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
