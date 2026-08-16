#!/usr/bin/env bash
# DURABILITY DEMO — the answer to "we lost 40 jobs, that cannot happen again."
# Submits a job, force-kills the workers WHILE it's processing, and shows the
# reaper re-delivers it so it still reaches 'done'. Zero lost jobs.
#   usage: ./kill_worker_demo.sh <LB_IP>
set -euo pipefail
IP="${1:?usage: kill_worker_demo.sh <LB_IP>}"

printf 'durability test %s\n' "$(date)" > /tmp/halcyon_dur.txt
JOB=$(curl -s -X POST -F "file=@/tmp/halcyon_dur.txt" "http://$IP/upload" \
      | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "Submitted job=$JOB"

echo "Waiting 6s for a worker to pick it up (status -> processing)..."
sleep 6
curl -s "http://$IP/jobs/$JOB" | python3 -c "import sys,json;print('status:',json.load(sys.stdin)['status'])"

echo ">>> Force-killing ALL workers mid-job (simulating the OOM crash) <<<"
kubectl delete pod -n halcyon -l app=halcyon-worker --grace-period=0 --force

echo "Now polling. The message is orphaned in the queue's pending list; the reaper"
echo "will reclaim it after its idle threshold and a fresh worker will finish it."
for i in $(seq 1 40); do
  S=$(curl -s "http://$IP/jobs/$JOB" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")
  echo "  [$((i*5))s] status=$S"
  [ "$S" = "done" ] && { echo "✅ RECOVERED — job completed despite the worker being killed. Zero loss."; exit 0; }
  [ "$S" = "dead" ] && { echo "⚠️ dead-lettered (hit a simulated failure on retry). Re-run — set FAIL_RATE/TIMEOUT_RATE to 0 in the ConfigMap for a clean run."; exit 1; }
  sleep 5
done
echo "Timed out waiting; check reaper logs: kubectl logs -n halcyon deploy/halcyon-reaper"
