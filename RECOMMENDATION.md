# Production Platform Recommendation — Halcyon Labs

Prepared for Dana and the CTO · Forward Deployed Engineering

## Recommendation (the short version)

Move off the single Droplet and onto the DOKS cluster you already have — but keep it
deliberately small. Run three things on the cluster: a stateless **API**, a pool of
**autoscaling workers**, and a tiny **reaper**. Keep the queue and database as **managed
DigitalOcean services** rather than self-hosting them. This directly fixes the four
things hurting you today — jobs lost on crash, no way to scale for the migration,
30-second deploy downtime, and no visibility — and it comes up entirely from code into
a clean account. Steady-state cost lands around **$210–260/month**: roughly 1.5–2×
today, nowhere near the 10× you're worried about.

One place I'd push back on your note: **don't run Postgres inside the cluster.** More on
that below — it's the most important decision here.

And the durability isn't theoretical. I built and deployed this, then **killed every
worker in the middle of a job — and it still completed, with nothing lost.**

## What I built, and the choices that mattered

The core idea is to separate the fast path (accepting an upload) from the slow path (the
20s–4min extraction), with a durable queue between them.

- **API — stateless, 2+ replicas.** Accepts the upload, records the job in Postgres,
  drops a work item on the queue, and returns immediately. Because it never holds the
  long-running work in memory, an upload burst can't run it out of memory the way last
  Tuesday's did.
- **Workers — autoscaling on queue depth.** Two run normally; up to ten spin up when the
  big customer's backlog builds, then scale back down. That's what absorbs "a few
  thousand contracts" without paying for idle machines the rest of the month. (Note: I
  scale on *queue depth*, not CPU — these workers spend most of their time waiting on the
  model, so CPU stays low even under a huge backlog.)
- **Durable queue (Valkey Streams) + Postgres as the source of truth.** A job is only
  removed from the queue after a worker finishes and commits the result. If a worker dies
  mid-job, the item stays pending and the **reaper** re-delivers it to a healthy worker.
  Postgres always holds the real state, so even a full cache loss can be rebuilt. This is
  the mechanism that makes losing 40 jobs impossible — and it's the part I tested by
  force-killing the workers.
- **Zero-downtime deploys.** Kubernetes rolls out new versions one pod at a time behind
  readiness checks, and workers finish their current job before exiting. No more
  SSH-at-night; deploys are safe during business hours and run from a pipeline.
- **The model call is wrapped** in a hard timeout, retries, and a dead-letter path, so
  "sometimes it just hangs" stops being an incident — a stuck call is bounded and retried
  instead of wedging a worker.
- **Observability.** Health endpoints, queue-depth and job metrics, and alerts on
  backlog, failures, and out-of-memory events — so you hear about a problem before a
  customer does.

Everything is reproducible from the repo: Terraform builds the cluster and managed
services; Kubernetes manifests deploy the app; a pipeline builds and ships the image.

## Where I disagree with your note: keep Postgres out of the cluster

Your CTO wants Postgres inside the cluster to avoid a managed-database bill. On a tight
runway I understand the instinct — but I'd advise against it, and it's the call I feel
most strongly about.

You told me two things that make self-run Postgres the riskiest thing you could own: you
**cannot lose this data**, and **none of the three engineers is an infrastructure
person.** Running a stateful database well on Kubernetes — backups, failover, version
upgrades, storage — is a specialised, ongoing job. Managed Postgres gives you automated
backups, point-in-time recovery, and failover for about **$15–40/month**. That's far less
than one lost-data incident with an enterprise account, and it removes a whole category
of 2 a.m. problems from a team with no one to handle them. If you want to self-host later
once you've hired for it, the design supports that — but for this migration, managed is
the right call.

## What I deliberately left out

A design at your size is mostly about what you *don't* build:

- No multi-region or DR beyond managed backups — single region is right for a six-week
  timeline and your budget.
- No service mesh, no blue-green — rolling updates are plenty at this scale.
- No deep multi-tenant isolation yet — I'd want to understand your compliance
  obligations first (see below).
- A dedicated least-privilege DB user — I used the built-in admin for now; adding a
  scoped app user is a pre-go-live task, not a blocker.
- Stream memory trimming — the queue log should be capped in production; noted.

These are deliberate omissions, not oversights. If any turn out to matter for the
enterprise contracts, each is straightforward to add.

## What it will cost

Rough monthly, steady-state:

| Item | ~ / month |
|---|---|
| Cluster nodes (2, autoscaling up during bursts) | $70–150 |
| Managed Postgres (smallest) | $15–30 |
| Managed Valkey (smallest) | $15 |
| Load balancer | $12 |
| Object storage + registry | $10 |
| **Infrastructure total** | **~$210–260** |

You actually come in **under** today's ~$400 with far more reliability. The honest
caveat: **inference will likely be your real cost driver, not infrastructure.** A few
thousand contracts each making a model call could dwarf the platform bill — I can't size
that without your token volumes, which is my top question below.

## What I'm still worried about / need from you

1. **The actual numbers.** "A few thousand contracts" over what window? Real peak
   concurrency? These drive worker and inference sizing.
2. **Inference cost and rate limits** at migration volume — the budget risk is here, not
   the servers.
3. **Data residency / PII / compliance** — contracts are sensitive. Where must this data
   live, how long do you keep it, what encryption is required?
4. **The SLA you actually signed** — uptime %, response times — so I can right-size
   redundancy.
5. **Tenant isolation** across the three enterprise customers.

## Your next six weeks

1. **Week 1:** get me the volume/concurrency and inference-token numbers so we size for
   the real peak.
2. Switch to managed Postgres and add a standby replica before go-live.
3. Add the scoped DB user; cap the queue stream length.
4. **Dress rehearsal:** replay a realistic burst of a few thousand jobs, watch it drain,
   confirm autoscaling behaviour and actual cost.
5. **On-call basics:** decide who gets paged on backlog/failure alerts and write a
   one-page runbook — with no infra person, this matters more than anything fancy.
6. Confirm compliance/residency and lock the region and retention policy.

I'd rather ship this — small, reliable, and honest about its limits — than a bigger
design three engineers can't operate. Happy to walk through any of it.
