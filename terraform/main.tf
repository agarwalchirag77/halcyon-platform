# =============================================================================
# Halcyon production platform — foundation (Step 1)
# VPC + DOKS + Managed Postgres + Managed Redis + Registry + Spaces
# Everything private-networked; DBs only reachable from the cluster.
# =============================================================================

# Always deploy the latest supported K8s patch — avoids pinning to a stale version.
data "digitalocean_kubernetes_versions" "current" {}

# Private network so the cluster <-> managed DBs traffic never touches public internet.
resource "digitalocean_vpc" "main" {
  name     = "${var.project_name}-vpc"
  region   = var.region
}

# ---- DOKS cluster --------------------------------------------------------
# auto_scale on the node pool = the cluster grows for the migration burst and
# shrinks back afterward (cost control + solves "ran out of memory / can't scale").
resource "digitalocean_kubernetes_cluster" "main" {
  name     = "${var.project_name}-cluster"
  region   = var.region
  version  = data.digitalocean_kubernetes_versions.current.latest_version
  vpc_uuid = digitalocean_vpc.main.id

  node_pool {
    name       = "${var.project_name}-workers"
    size       = var.node_size
    auto_scale = true
    min_nodes  = var.node_min
    max_nodes  = var.node_max
  }

  # Keeps kubeconfig token fresh via doctl instead of a static long-lived cred.
  destroy_all_associated_resources = true
}

# ---- Managed Postgres ----------------------------------------------------
# Recommended OVER in-cluster (see blueprint §4): backups, PITR, failover, patching.
# node_count = 1 for the exercise budget; bump to 2 for HA standby before go-live.
resource "digitalocean_database_cluster" "postgres" {
  name                 = "${var.project_name}-pg"
  engine               = "pg"
  version              = "16"
  size                 = var.pg_size
  region               = var.region
  node_count           = 1
  private_network_uuid = digitalocean_vpc.main.id
}

resource "digitalocean_database_db" "app" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = "halcyon"
}


# Firewall: only the DOKS cluster may reach Postgres (defense in depth).
resource "digitalocean_database_firewall" "postgres" {
  cluster_id = digitalocean_database_cluster.postgres.id
  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.main.id
  }
}

# ---- Managed Valkey (Redis-compatible) — durable queue backing store -----
# DO migrated managed Redis -> Valkey (drop-in Redis protocol), so our queue
# client code is unchanged. Managed (not in-cluster) = persistence + failover,
# so the QUEUE ITSELF survives a node failure instead of repeating Dana's disaster.
resource "digitalocean_database_cluster" "redis" {
  name                 = "${var.project_name}-valkey"
  engine               = "valkey"
  version              = "8"
  size                 = var.redis_size
  region               = var.region
  node_count           = 1
  private_network_uuid = digitalocean_vpc.main.id
}

resource "digitalocean_database_firewall" "redis" {
  cluster_id = digitalocean_database_cluster.redis.id
  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.main.id
  }
}

# ---- Container registry (CI pushes images here; cluster pulls) -----------
resource "digitalocean_container_registry" "main" {
  name                   = "${var.project_name}-registry"
  subscription_tier_slug = "basic" # ~$5/mo
  region                 = var.region
}

# ---- Spaces bucket (durable object storage for uploaded PDFs) ------------
# Only created if Spaces keys are provided; workers on any node can read files.
resource "digitalocean_spaces_bucket" "uploads" {
  count  = var.spaces_access_id == "" ? 0 : 1
  name   = "${var.project_name}-uploads"
  region = var.region
  acl    = "private"
}
