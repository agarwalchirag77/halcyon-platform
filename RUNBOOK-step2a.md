# Step 2a — Build the app image and push it to your registry

Goal: turn the `app/` code into a container image in your DO registry, so Step 2b
can deploy it. ~5–10 min.

## Requires Docker
You need Docker Desktop running locally. Check:
```
docker version
```
If you DON'T have Docker, tell me — we'll switch to a GitHub Actions workflow that
builds + pushes for you (that also ticks the CI/CD box the exercise wants).

## Commands
```
# 1. Let Docker authenticate to your DO registry
doctl registry login

# 2. Build. --platform linux/amd64 forces an image that matches the cluster nodes
#    (important if you're ever on an Apple-Silicon Mac).
cd halcyon-platform/app
docker build --platform linux/amd64 \
  -t registry.digitalocean.com/halcyon-registry/halcyon:v1 .

# 3. Push
docker push registry.digitalocean.com/halcyon-registry/halcyon:v1

# 4. Verify the tag is in your registry
doctl registry repository list-tags halcyon
```

✅ Success = `list-tags` shows `v1`.

## What to send me
- Output of `doctl registry repository list-tags halcyon` (should list `v1`), or
- Any build/push error (paste it — we'll fix together), or
- "no Docker" and I'll generate the GitHub Actions build pipeline instead.

Next (Step 2b): create the app Secret from your Terraform outputs, install KEDA,
apply the K8s manifests (API + workers + reaper + autoscaling + probes), and get
your live LoadBalancer URL.
