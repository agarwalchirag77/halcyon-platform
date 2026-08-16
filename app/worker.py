"""Async worker: consumes jobs from the Valkey stream and 'processes' them.

Durability model:
  - Read via consumer group (XREADGROUP) => each message is tracked in the group's
    Pending Entries List (PEL) until we XACK it.
  - We only XACK AFTER the work is committed to Postgres. So if this worker is killed
    mid-job, the message stays pending and the reaper re-delivers it => no lost jobs.
  - Transient failures/timeouts => explicit retry (XACK + re-XADD) up to MAX_ATTEMPTS,
    then dead-letter. Two clean mechanisms, each easy to explain.
"""
import os, sys, time, signal, random, socket
import httpx
import config, store

CONSUMER = os.environ.get("HOSTNAME", socket.gethostname())  # unique per pod
_stop = False

def _handle_sigterm(*_):
    # Graceful shutdown: stop taking NEW work, let the current job finish, then exit.
    global _stop
    _stop = True
    print("SIGTERM received — draining, will exit after current job", flush=True)

signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

def call_inference():
    """Real call to DO Serverless Inference (OpenAI-compatible), with a hard timeout."""
    if not config.INFERENCE_API_KEY:
        return  # allow running without a key while wiring things up
    with httpx.Client(timeout=config.INFERENCE_TIMEOUT) as c:
        resp = c.post(
            f"{config.INFERENCE_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.INFERENCE_API_KEY}"},
            json={
                "model": config.INFERENCE_MODEL,
                "messages": [{"role": "user",
                              "content": "Extract obligations, dates and renewal terms. Reply OK."}],
                "max_tokens": 16,
            },
        )
        resp.raise_for_status()

def do_work(job_id: str):
    """Simulate contract extraction: variable duration, occasional hang/failure, one model call."""
    store.set_status(job_id, "processing")

    # Simulated model hang -> our httpx timeout / this raise is what makes 'it just hangs' safe.
    if random.random() < config.TIMEOUT_RATE:
        raise TimeoutError("simulated model hang")

    # Sleep in 1s slices so a graceful SIGTERM between jobs is responsive.
    duration = random.randint(config.SLEEP_MIN, config.SLEEP_MAX)
    for _ in range(duration):
        time.sleep(1)

    if random.random() < config.FAIL_RATE:
        raise RuntimeError("simulated extraction failure")

    call_inference()
    store.set_status(job_id, "done")

def handle(msg_id: str, job_id: str):
    try:
        do_work(job_id)
        store.r.xack(config.STREAM, config.GROUP, msg_id)   # success -> remove from PEL
        print(f"done job={job_id} msg={msg_id}", flush=True)
    except Exception as e:
        attempts = store.increment_attempts(job_id)
        store.r.xack(config.STREAM, config.GROUP, msg_id)   # ack this delivery...
        if attempts >= config.MAX_ATTEMPTS:
            store.set_status(job_id, "dead", error=str(e))
            store.r.xadd(config.DLQ_STREAM, {"job_id": job_id, "error": str(e)})
            print(f"DEAD-LETTER job={job_id} attempts={attempts} err={e}", flush=True)
        else:
            store.r.xadd(config.STREAM, {"job_id": job_id})  # ...and re-enqueue a fresh retry
            print(f"retry job={job_id} attempts={attempts} err={e}", flush=True)

def main():
    store.init_db()
    store.ensure_group()
    print(f"worker {CONSUMER} started", flush=True)
    while not _stop:
        resp = store.r.xreadgroup(
            config.GROUP, CONSUMER, {config.STREAM: ">"}, count=1, block=5000
        )
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                handle(msg_id, fields["job_id"])
    print(f"worker {CONSUMER} exiting cleanly", flush=True)
    sys.exit(0)

if __name__ == "__main__":
    main()
