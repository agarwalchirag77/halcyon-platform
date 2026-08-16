"""Central config, all from env vars (12-factor). Nothing secret is hard-coded."""
import os

# Injected from the Kubernetes Secret we build from Terraform outputs.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
REDIS_URL    = os.environ.get("REDIS_URL", "")   # Valkey (Redis protocol); DO uses rediss:// (TLS)

# DO Serverless Inference (OpenAI-compatible). Key is generated against the $200 credits.
INFERENCE_BASE_URL = os.environ.get("INFERENCE_BASE_URL", "https://inference.do-ai.run")
INFERENCE_API_KEY  = os.environ.get("INFERENCE_API_KEY", "")
INFERENCE_MODEL    = os.environ.get("INFERENCE_MODEL", "llama3.3-70b-instruct")
INFERENCE_TIMEOUT  = float(os.environ.get("INFERENCE_TIMEOUT", "30"))  # hard cap so a hang can't wedge a worker

# Queue (Valkey Streams)
STREAM     = os.environ.get("JOB_STREAM", "jobs")
GROUP      = os.environ.get("JOB_GROUP", "workers")
DLQ_STREAM = os.environ.get("DLQ_STREAM", "jobs:dlq")

# Retry / failure policy
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))

# Simulated workload knobs (the exercise: sleep 20s-4min, sometimes timeout, sometimes fail).
# For a fast durability demo, override SLEEP_MAX low (e.g. 30) so recovery is visible in ~1 min.
SLEEP_MIN    = int(os.environ.get("SLEEP_MIN", "20"))
SLEEP_MAX    = int(os.environ.get("SLEEP_MAX", "240"))
FAIL_RATE    = float(os.environ.get("FAIL_RATE", "0.1"))     # ~10% permanent-ish failures
TIMEOUT_RATE = float(os.environ.get("TIMEOUT_RATE", "0.1"))  # ~10% simulated model hangs

# Reaper: reclaim messages orphaned by a crashed worker. MUST exceed max job time,
# else it would steal a job a live worker is still processing (double-processing).
REAPER_MIN_IDLE_MS = int(os.environ.get("REAPER_MIN_IDLE_MS", "300000"))  # 5 min default
