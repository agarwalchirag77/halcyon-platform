# Halcyon Labs — Production Platform (DigitalOcean FDE Exercise)

A production-ready platform for Halcyon's contract-extraction workload: customers upload
PDFs, a model extracts obligations/dates/renewal terms, and structured output comes back.
Built to fix the four problems in Dana's note — **lost jobs on crash, no way to scale for
the migration, 30-second deploy downtime, and no visibility** — while staying small enough
for a nine-person team with no infrastructure hire.

**👉 Start with [`RECOMMENDATION.md`](./RECOMMENDATION.md)** — the write-up for Dana. This
repo is the evidence behind it.

---

## Architecture (one paragraph)

Uploads hit a stateless **API** that records the job in **Postgres** (the source of truth),
drops a work item on a **Valkey Streams** queue, and returns immediately. A pool of
**workers** consumes the queue, calls the model with a hard timeout, and writes results
back — acknowledging the message *only after* the result is committed. A small **reaper**
re-delivers any job orphaned by a crashed worker. Workers **autoscale on queue depth**
(KEDA), the API runs behind a DO load balancer with **zero-downtime rolling deploys**, and
Postgres/Valkey are **managed services**. Everything comes up from code (Terraform + K8s
manifests) into a clean DigitalOcean account.

```
client → LB → API (stateless, HPA) → Postgres (source of truth)
                     │ enqueue
                     ▼
              Valkey Streams  →  Workers (autoscale on queue depth)  →  DO Serverless Inference
                     ▲                         │ ack-after-commit
                     └──── Reaper (re-delivers orphaned jobs) ────┘
```

---

## Try it yourself (live system)

The API is live at **http://152.42.158.139**

```bash
IP=152.42.158.139

# 1. health check
curl -i http://$IP/healthz

# 2. submit a "contract" (any file) — returns a job_id immediately
echo "sample contract" > sample.txt
curl -s -X POST -F "file=@sample.txt" http://$IP/upload

# 3. poll the job — status goes queued → processing → done (usually within ~30s)
curl -s http://$IP/jobs/<paste-job_id-here>

# 4. metrics (Prometheus format)
curl -s http://$IP/metrics | grep halcyon
```

You should see the upload return a `job_id` instantly (the API never blocks on the
20s–4min processing), and the job reach `"status":"done"` a little later.

---

## Prove the important properties

These require `kubectl` access to the cluster (happy to give read-only access or
screen-share during the review). Both scripts take the LB IP as an argument.

```bash
chmod +x scripts/*.sh

# Durability — the core of the brief:
# submit a job, force-kill ALL workers mid-process, and watch the reaper re-deliver it
# so it still completes. Zero lost jobs.
./scripts/kill_worker_demo.sh 152.42.158.139

# Autoscaling under load:
# fire a burst of uploads and watch KEDA scale workers on queue depth, then back down.
./scripts/load_test.sh 152.42.158.139 200
kubectl get pods -n halcyon -w
```

Other production properties in the code:
- **Zero-downtime deploys** — `kubectl rollout restart deploy/halcyon-api -n halcyon`
  while hitting `/healthz` in a loop: continuous `200`s (readiness probes + `maxUnavailable=0`).
- **Timeouts / retries / dead-letter** on the model call (see `app/worker.py`).
- **Memory limits** on workers (the direct fix for the OOM incident).

---

## Reproduce from scratch (comes up from code)

Full step-by-step is in the runbooks. Summary:

| Step | Runbook | What it does |
|---|---|---|
| 1 | `RUNBOOK-step1.md`  | Terraform: VPC, DOKS, Managed Postgres, Managed Valkey, registry |
| 2a | `RUNBOOK-step2a.md` | Build + push the container image |
| 2b | `RUNBOOK-step2b.md` | Deploy API + workers + reaper; get the live endpoint |
| 2c | `RUNBOOK-step2c.md` | KEDA autoscaling + the durability & load demos |

```bash
# infrastructure
cd terraform && terraform init && terraform apply
# then follow RUNBOOK-step2a/2b/2c for the app + autoscaling
```

Tear down when finished: `cd terraform && terraform destroy`.

---

## Repository layout

```
terraform/           Infrastructure as code (cluster, managed DBs, registry, VPC)
app/                 API + async worker + reaper (one image, three roles) + Dockerfile
k8s/                 Kubernetes manifests (API+LB+HPA, worker, reaper, KEDA autoscaler)
scripts/             Durability demo + burst load test
RECOMMENDATION.md    ← the deliverable: the write-up for Dana
RUNBOOK-step*.md     Step-by-step reproduction guides
```


