"""Reaper: recovers jobs orphaned by a crashed/killed worker.

When a worker dies mid-job it never XACKs, so the message sits in the consumer
group's Pending Entries List (PEL). XAUTOCLAIM hands any message idle longer than
REAPER_MIN_IDLE_MS to this reaper, which re-enqueues it for a live worker and acks
the stale entry. This is the guarantee behind 'we will never lose 40 jobs again'.

Why min-idle must exceed max job time: a legitimately long (4-min) job is 'pending'
the whole time it runs. If min-idle were shorter, the reaper would steal a job a live
worker is still processing -> double work. So min-idle > longest job.
"""
import time
import config, store

def main():
    store.ensure_group()
    print(f"reaper started (min_idle={config.REAPER_MIN_IDLE_MS}ms)", flush=True)
    cursor = "0-0"
    while True:
        # Claim up to 10 stale pending messages at a time.
        cursor, claimed, _ = store.r.xautoclaim(
            config.STREAM, config.GROUP, "reaper",
            min_idle_time=config.REAPER_MIN_IDLE_MS, start_id=cursor, count=10,
        )
        for msg_id, fields in claimed:
            job_id = fields.get("job_id")
            if not job_id:
                store.r.xack(config.STREAM, config.GROUP, msg_id)
                continue
            store.r.xadd(config.STREAM, {"job_id": job_id})     # re-deliver to a live worker
            store.r.xack(config.STREAM, config.GROUP, msg_id)   # clear the orphaned entry
            print(f"reaped orphaned job={job_id} (worker died mid-job) -> re-enqueued", flush=True)
        if cursor == "0-0":
            time.sleep(10)  # caught up; poll periodically

if __name__ == "__main__":
    main()
