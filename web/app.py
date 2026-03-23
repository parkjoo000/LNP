"""
LNP Data Pipeline — FastAPI web interface.
Entry point: uvicorn web.app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import os
import queue
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("web.app")

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT / "output" / "lnp_data.db")
LOGS_DIR = str(ROOT / "output" / "logs")
EXPORTS_DIR = str(ROOT / "output" / "exports")
INPUT_RAW = str(ROOT / "input" / "raw")

app = FastAPI(title="LNP Data Pipeline", version="1.0.0")

# Serve static files
_static = ROOT / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_static)), name="static")

# Per-run SSE queues
_run_queues: dict[str, queue.Queue] = {}


@app.get("/")
async def index():
    return FileResponse(str(_static / "index.html"))


# ─── Upload & pipeline trigger ────────────────────────────────────────────────

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Accept a CSV file, save to input/raw/, run pipeline, return run_id."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    run_id = str(uuid.uuid4())[:8]
    dest = os.path.join(INPUT_RAW, file.filename)

    os.makedirs(INPUT_RAW, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    q: queue.Queue = queue.Queue()
    _run_queues[run_id] = q

    # Inject queue into pipeline module so it can emit events
    import pipeline as pl
    pl._sse_queue = q

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_pipeline_sync, dest, run_id)

    return JSONResponse({"run_id": run_id, "filename": file.filename})


def _run_pipeline_sync(file_path: str, run_id: str):
    import pipeline as pl
    try:
        pl.run_pipeline(file_path, run_id=run_id)
    except Exception as exc:
        logger.error("Pipeline error for %s: %s", run_id, exc)
    finally:
        q = _run_queues.get(run_id)
        if q:
            q.put(None)  # sentinel


# ─── SSE progress stream ──────────────────────────────────────────────────────

@app.get("/progress/{run_id}")
async def progress(run_id: str):
    q = _run_queues.get(run_id)
    if q is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        while True:
            try:
                item = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: q.get(timeout=30)
                )
            except Exception:
                yield "data: {\"event\": \"timeout\"}\n\n"
                break
            if item is None:
                yield "data: {\"event\": \"done\"}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Data queries ─────────────────────────────────────────────────────────────

def _open_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not initialised")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/batches")
async def list_batches():
    try:
        conn = _open_db()
    except HTTPException:
        return JSONResponse([])
    try:
        rows = conn.execute("SELECT * FROM Batch ORDER BY batch_id").fetchall()
        return JSONResponse([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/results/{batch_id}")
async def get_results(batch_id: str):
    conn = _open_db()
    try:
        result = {}
        for table in ("AssayResults_Physical", "InVivo_FLUC", "InVivo_EPO", "Toxicity"):
            try:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE batch_id = ?", (batch_id,)  # noqa: S608
                ).fetchall()
                if rows:
                    result[table] = [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass
        return JSONResponse(result)
    finally:
        conn.close()


# ─── Export ───────────────────────────────────────────────────────────────────

@app.post("/export")
async def export():
    import importlib.util
    skills = ROOT / ".claude" / "skills"
    spec = importlib.util.spec_from_file_location(
        "export_excel",
        str(skills / "db-writer" / "scripts" / "export_excel.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        path = mod.export_excel(DB_PATH, EXPORTS_DIR)
        return FileResponse(path, filename=os.path.basename(path),
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Logs ─────────────────────────────────────────────────────────────────────

@app.get("/logs")
async def list_logs():
    os.makedirs(LOGS_DIR, exist_ok=True)
    files = sorted(
        f for f in os.listdir(LOGS_DIR) if f.endswith(".log")
    )
    return JSONResponse(files)


@app.get("/logs/{filename}")
async def get_log(filename: str):
    # Sanitise: no path traversal
    safe = os.path.basename(filename)
    path = os.path.join(LOGS_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Log not found")
    with open(path) as f:
        content = f.read()
    return JSONResponse({"filename": safe, "content": content})
