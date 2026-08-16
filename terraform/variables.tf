variable "do_token" {
  description = "DigitalOcean API token (set via env: export TF_VAR_do_token=...)"
  type        = string
  sensitive   = true
}

# Spaces keys are optional for Step 1 — only needed once the app stores uploaded files.
# Create them in DO console: API > Spaces Keys. Leave blank for now if you want.
variable "spaces_access_id" {
  description = "DO Spaces access key ID (env: TF_VAR_spaces_access_id)"
  type        = string
  sensitive   = true
  default     = ""
}
variable "spaces_secret_key" {
  description = "DO Spaces secret key (env: TF_VAR_spaces_secret_key)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "region" {
  description = "DO region. BLR1 = Bangalore (India data residency)."
  type        = string
  default     = "blr1"
}

variable "project_name" {
  description = "Prefix for all resources so they're easy to find/destroy."
  type        = string
  default     = "halcyon"
}

# Worker/API node pool. Autoscales with load, scales back down to control cost.
variable "node_size" {
  description = "Droplet size for cluster nodes."
  type        = string
  default     = "s-2vcpu-4gb" # ~$24/node/mo; enough for API + a few workers
}
variable "node_min" {
  type    = number
  default = 2 # baseline (also gives us spread for zero-downtime deploys)
}
variable "node_max" {
  type    = number
  default = 5 # headroom for the migration burst; autoscaler adds only when needed
}

# Smallest managed DB tiers keep us near the $400/mo target. Bump later if needed.
variable "pg_size" {
  type    = string
  default = "db-s-1vcpu-1gb" # ~$15/mo
}
variable "redis_size" {
  type    = string
  default = "db-s-1vcpu-1gb" # ~$15/mo
}
