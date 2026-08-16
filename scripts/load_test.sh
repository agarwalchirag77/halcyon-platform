#!/usr/bin/env bash
# Burst load test: fire N uploads to prove the queue absorbs a spike and KEDA
# scales workers up, then back down after the backlog drains.
#   usage: ./load_test.sh <LB_IP> [N]
set -euo pipefail
IP="${1:?usage: load_test.sh <LB_IP> [N]}"
N="${2:-200}"

printf 'sample contract %s\n' "$(date)" > /tmp/halcyon_load.txt
echo "Submitting $N jobs to http://$IP/upload ..."
for i in $(seq 1 "$N"); do
  curl -s -X POST -F "file=@/tmp/halcyon_load.txt" "http://$IP/upload" > /dev/null &
  (( i % 25 == 0 )) && wait   # 25 parallel at a time
done
wait
echo "Done submitting $N jobs."
echo "Now watch workers scale on queue lag:"
echo "  kubectl get pods -n halcyon -w"
echo "  kubectl get scaledobject -n halcyon halcyon-worker-scaler"
echo "  watch -n2 'curl -s http://$IP/metrics | grep halcyon_queue_depth'"
