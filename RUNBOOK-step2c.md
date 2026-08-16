# Step 2c — Autoscaling (KEDA) + the two demos

Run from `halcyon-platform/`. `IP` = your LoadBalancer IP from Step 2b.

## A. Install KEDA (queue-based autoscaler)
```
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda -n keda --create-namespace
kubectl get pods -n keda           # wait until Running
```

## B. Wire KEDA to your Valkey queue
Derive host/port/password from your Terraform output and create the auth secret:
```
RD_URL=$(cd terraform && terraform output -raw redis_uri | sed 's/%$//')
RD_HOST=$(echo "$RD_URL" | sed -E 's#rediss?://[^@]*@([^:]+):.*#\1#')
RD_PORT=$(echo "$RD_URL" | sed -E 's#.*@[^:]+:([0-9]+).*#\1#')
RD_PASS=$(echo "$RD_URL" | sed -E 's#rediss?://[^:]+:([^@]+)@.*#\1#')
echo "host=$RD_HOST port=$RD_PORT"     # sanity check (password intentionally not printed)

kubectl create secret generic keda-redis-auth -n halcyon --from-literal=password="$RD_PASS"

# put your host:port into the ScaledObject (macOS sed syntax):
sed -i '' "s/REPLACE_HOST:REPLACE_PORT/$RD_HOST:$RD_PORT/" k8s/50-keda.yaml

kubectl apply -f k8s/50-keda.yaml
kubectl get scaledobject -n halcyon    # READY=True, ACTIVE reflects queue lag
```
KEDA now owns the worker replica count (it overrides the Deployment's `replicas`).

## C. DEMO 1 — Durability (the money shot)
Optional but recommended for a clean run: turn off random failures so the recovered
job is guaranteed to finish, then restore afterward.
```
kubectl patch configmap halcyon-config -n halcyon --type merge \
  -p '{"data":{"FAIL_RATE":"0","TIMEOUT_RATE":"0"}}'
kubectl rollout restart deploy/halcyon-worker -n halcyon
```
Run it:
```
chmod +x scripts/*.sh
./scripts/kill_worker_demo.sh $IP
```
What you'll narrate: job goes to `processing` → we force-kill all workers mid-job →
the message is orphaned in the consumer group's pending list → the **reaper**
`XAUTOCLAIM`s it after the idle threshold → a fresh worker finishes it → `done`.
**Zero lost jobs** — the literal answer to Dana's incident.

In a second terminal you can show the mechanics:
```
kubectl logs -n halcyon deploy/halcyon-reaper -f     # "reaped orphaned job=... -> re-enqueued"
```
Restore failure simulation when done:
```
kubectl patch configmap halcyon-config -n halcyon --type merge \
  -p '{"data":{"FAIL_RATE":"0.1","TIMEOUT_RATE":"0.1"}}'
kubectl rollout restart deploy/halcyon-worker -n halcyon
```

## D. DEMO 2 — Burst load + autoscaling
```
./scripts/load_test.sh $IP 200
# watch in another pane:
kubectl get pods -n halcyon -w                  # workers scale 2 -> up to 10, then back to 2
kubectl get scaledobject -n halcyon
```
Narration: a spike lands, the queue lag rises, KEDA scales workers up to drain it,
then scales back to the warm baseline after `cooldownPeriod`. This is how the
"biggest customer uploads thousands of contracts" scenario is absorbed without
paying for idle capacity the rest of the time.

## E. Zero-downtime deploy (optional third proof)
```
# in one pane, hammer the API:
while true; do curl -s -o /dev/null -w "%{http_code}\n" http://$IP/healthz; sleep 0.3; done
# in another, trigger a rolling deploy:
kubectl rollout restart deploy/halcyon-api -n halcyon
```
You should see continuous `200`s with no failures — readiness probes + maxUnavailable=0.

## What to send me
- The final line of the durability demo (hopefully `✅ RECOVERED ...`)
- `kubectl get pods -n halcyon` during the load test (showing >2 workers)
- Any errors (KEDA `ScaledObject` not READY is the likely one — usually the TLS/auth;
  paste `kubectl describe scaledobject -n halcyon halcyon-worker-scaler`)

## Known follow-ups to mention in the review (deliberate omissions)
- The Valkey stream isn't trimmed yet; production would `XTRIM`/MAXLEN to cap memory.
- Single-node managed DB/Valkey for the exercise; add standbys for real HA.
- Reaper idle threshold is tuned to the demo's short jobs; set it >4min for real jobs.
