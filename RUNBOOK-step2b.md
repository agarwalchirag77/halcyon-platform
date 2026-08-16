# Step 2b — Deploy the app to the cluster and get a live endpoint

Run these from `halcyon-platform/`. ~5–10 min (the DO load balancer takes a couple
minutes to get a public IP).

## 1. Namespace
```
kubectl apply -f k8s/00-namespace.yaml
```

## 2. Registry pull secret (lets the cluster pull your private image)
```
doctl registry kubernetes-manifest --namespace halcyon | kubectl apply -f -
kubectl get secret -n halcyon | grep registry
```
Confirm the secret is named `registry-halcyon-registry` (that's what the manifests
reference). If it's named differently, tell me and we'll adjust one line.

## 3. App secret (DB + queue URIs pulled straight from Terraform outputs)
```
cd terraform
DB_URL=$(terraform output -raw postgres_uri)
RD_URL=$(terraform output -raw redis_uri)
cd ..
kubectl create secret generic halcyon-secrets -n halcyon \
  --from-literal=DATABASE_URL="$DB_URL" \
  --from-literal=REDIS_URL="$RD_URL" \
  --from-literal=INFERENCE_API_KEY=""      # leave blank for now; add your DO key later
```
(The worker skips the real model call while the key is blank, so we can validate the
pipeline first, then add inference.)

## 4. Deploy config + app
```
kubectl apply -f k8s/10-config.yaml
kubectl apply -f k8s/20-api.yaml
kubectl apply -f k8s/30-worker.yaml
kubectl apply -f k8s/40-reaper.yaml
```

## 5. Watch it come up
```
kubectl get pods -n halcyon -w
```
Expect: 2 `halcyon-api`, 2 `halcyon-worker`, 1 `halcyon-reaper` -> all `Running`.
(Ctrl-C to stop watching.) If a pod is stuck `ImagePullBackOff`, the pull secret name
is wrong — see step 2.

## 6. Get your public URL (DO load balancer)
```
kubectl get svc -n halcyon halcyon-api
```
Wait until `EXTERNAL-IP` shows an IP (not `<pending>`) — ~1–2 min.

## 7. Smoke test the pipeline
```
IP=$(kubectl get svc -n halcyon halcyon-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "test contract" > sample.txt

# submit a job
curl -s -X POST -F "file=@sample.txt" http://$IP/upload
# -> {"job_id":"....","status":"queued"}

# poll it (status goes queued -> processing -> done within ~30s)
curl -s http://$IP/jobs/<paste-job_id>
```
Also check health + metrics:
```
curl -s http://$IP/healthz
curl -s http://$IP/metrics | grep halcyon
```

## What to send me
- `kubectl get pods -n halcyon`  (all Running?)
- The `curl .../upload` response and a `curl .../jobs/<id>` showing it reach `done`
- Any pod errors (`kubectl logs -n halcyon deploy/halcyon-worker` is the useful one)

Then Step 2c: install KEDA for queue-based worker autoscaling, run the burst load test,
and the **kill-a-worker durability demo** (submit a job, kill the worker mid-process,
watch the reaper re-enqueue it and the job still reach `done` = zero lost jobs).
