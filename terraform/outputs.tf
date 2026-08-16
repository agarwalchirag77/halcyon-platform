# Sensitive outputs are marked so they don't print to the terminal.
# Retrieve with:  terraform output -raw <name>

output "cluster_id" {
  value = digitalocean_kubernetes_cluster.main.id
}

output "cluster_name" {
  value = digitalocean_kubernetes_cluster.main.name
}

output "registry_endpoint" {
  value = digitalocean_container_registry.main.endpoint
}

output "postgres_uri" {
  description = "Private connection URI for the app (VPC-only)."
  value       = digitalocean_database_cluster.postgres.private_uri
  sensitive   = true
}

output "redis_uri" {
  description = "Private connection URI for the durable queue (VPC-only)."
  value       = digitalocean_database_cluster.redis.private_uri
  sensitive   = true
}

output "spaces_bucket" {
  # Key off the resource count, not the sensitive var, so the output stays non-sensitive.
  value = length(digitalocean_spaces_bucket.uploads) > 0 ? digitalocean_spaces_bucket.uploads[0].name : "(skipped — no Spaces keys set)"
}
