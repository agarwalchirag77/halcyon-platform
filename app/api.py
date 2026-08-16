"""Upload API. Decouples the fast HTTP path from the slow (20s-4min) processing.

Flow: accept file -> record job in Postgres (source of truth) -> enqueue a work
signal on Valkey -> return immediately. The API never blocks on processing, so a
big upload burst can't exhaust its memory (this is the fix for Dana's OOM).
"""
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import store

app = FastAPI(title="Halcyon Ingest API")

UPLOADS = Counter("halcyon_uploads_total", "Files accepted for processing")
QUEUE_DEPTH = Gauge("halcyon_queue_depth", "Current work-queue depth")

@app.on_event("startup")
def _startup():
    store.init_db()
    store.ensure_group()

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # We only need metadata for the simulation — we intentionally do NOT parse the PDF
    # (per the brief). In production the bytes would go to Spaces and the worker would
    # fetch them; here we record the filename and enqueue.
    job_id = str(uuid.uuid4())
    store.create_job(job_id, file.filename or "unknown.pdf")
    store.enqueue(job_id)
    UPLOADS.inc()
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job

@app.get("/healthz")   # liveness: is the process up?
async def healthz():
    return {"ok": True}

@app.get("/readyz")    # readiness: can we actually serve (deps reachable)?
async def readyz():
    if store.db_ok() and store.redis_ok():
        return {"ready": True}
    raise HTTPException(status_code=503, detail="dependencies not ready")

@app.get("/metrics")
async def metrics():
    QUEUE_DEPTH.set(store.queue_depth())
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
