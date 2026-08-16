# Step 1 — Stand up the foundation (VPC, DOKS, Postgres, Redis, Registry)

Goal: reproduce the base platform from code into your DO account, then confirm the
cluster is reachable. ~15–25 min (most of it is DO provisioning the managed DBs).

## 1a. Install the tools (once)
You need: `terraform`, `doctl` (DO CLI), `kubectl`, `helm`.

macOS (Homebrew):
```
brew install terraform doctl kubernetes-cli helm
```
(If you'd rather not install locally, DigitalOcean's browser **Cloud Shell** has
kubectl/doctl preinstalled — tell me and I'll adapt the steps.)

## 1b. Create your API token (keep it private — don't paste it to me)
DO console → **API → Tokens → Generate New Token** (name it `halcyon-fde`, full access).
Copy it once. Then in your terminal:
```
export TF_VAR_do_token="dop_v1_...."      # paste your token here
doctl auth init --access-token "$TF_VAR_do_token"
```
(Spaces keys are optional for Step 1 — skip unless you want the bucket now.)

## 1c. Apply the Terraform
```
cd halcyon-platform/terraform
terraform init
terraform plan          # read what it will create — sanity check
terraform apply         # type "yes"; provisioning the managed DBs takes ~5–10 min
```
Expected: 1 VPC, 1 DOKS cluster, 1 Postgres cluster (+ db + user + firewall),
1 Redis cluster (+ firewall), 1 container registry.

## 1d. Connect kubectl to the new cluster
```
doctl kubernetes cluster kubeconfig save halcyon-cluster
kubectl get nodes
```
✅ Success = you see 2 nodes in `Ready` state.

## 1e. Grab the connection strings (we'll use them for the app in Step 2)
```
terraform output -raw postgres_uri
terraform output -raw redis_uri
terraform output registry_endpoint
```

## When you're done for the day (stops billing)
```
terraform destroy
```

---
### What to send me after this step
- The output of `kubectl get nodes`
- Any error from `terraform apply` (paste it — we'll fix together)

I'll also verify the cluster/resources appear in your DO console (read-only) while you run this.
Then we move to Step 2: the app (FastAPI API + async worker sim) + Helm + autoscaling + the durability demo.
