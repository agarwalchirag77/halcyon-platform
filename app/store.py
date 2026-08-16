"""State layer: Postgres = source of truth for jobs; Valkey = work queue.

Key idea for durability: the job's real state lives in Postgres. The Valkey stream
is only a *work signal*. If Valkey ever lost data, we could rebuild the queue from
Postgres (rows still in 'queued'/'processing'). That's why losing a worker — or even
the cache — never loses a job.
"""
import psycopg
from psycopg_pool import ConnectionPool
import redis
import config

# --- Postgres ---------------------------------------------------------------
_pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=10, open=True)

def init_db():
    with _pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          UUID PRIMARY KEY,
                filename    TEXT,
                status      TEXT NOT NULL DEFAULT 'queued',  -- queued|processing|done|dead
                attempts    INT  NOT NULL DEFAULT 0,
                error       TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")

def create_job(job_id: str, filename: str):
    with _pool.connection() as conn:
        conn.execute(
            "INSERT INTO jobs (id, filename, status) VALUES (%s, %s, 'queued')",
            (job_id, filename),
        )

def set_status(job_id: str, status: str, error: str | None = None):
    with _pool.connection() as conn:
        conn.execute(
            "UPDATE jobs SET status=%s, error=%s, updated_at=now() WHERE id=%s",
            (status, error, job_id),
        )

def increment_attempts(job_id: str) -> int:
    with _pool.connection() as conn:
        row = conn.execute(
            "UPDATE jobs SET attempts=attempts+1, updated_at=now() WHERE id=%s RETURNING attempts",
            (job_id,),
        ).fetchone()
        return row[0] if row else 0

def get_job(job_id: str):
    with _pool.connection() as conn:
        row = conn.execute(
            "SELECT id, filename, status, attempts, error, created_at, updated_at FROM jobs WHERE id=%s",
            (job_id,),
        ).fetchone()
        if not row:
            return None
        cols = ["id", "filename", "status", "attempts", "error", "created_at", "updated_at"]
        return {c: (str(v) if v is not None else None) for c, v in zip(cols, row)}

def counts_by_status() -> dict:
    with _pool.connection() as conn:
        rows = conn.execute("SELECT status, count(*) FROM jobs GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}

def db_ok() -> bool:
    try:
        with _pool.connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False

# --- Valkey (Redis protocol) ------------------------------------------------
r = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)

def ensure_group():
    """Create the consumer group once; ignore 'already exists'."""
    try:
        r.xgroup_create(config.STREAM, config.GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

def enqueue(job_id: str):
    r.xadd(config.STREAM, {"job_id": job_id})

def queue_depth() -> int:
    try:
        return r.xlen(config.STREAM)
    except Exception:
        return -1

def redis_ok() -> bool:
    try:
        r.ping()
        return True
    except Exception:
        return False
