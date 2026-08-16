# Pins Terraform + the DigitalOcean provider so the build is reproducible
# into a clean account (a hard requirement of the exercise: "comes up from code").
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.43"
    }
  }
}

provider "digitalocean" {
  # Token is read from the env var TF_VAR_do_token — NEVER hard-code it or commit it.
  token = var.do_token

  # Spaces (object storage) uses a separate access key/secret, also from env vars.
  spaces_access_id  = var.spaces_access_id
  spaces_secret_key = var.spaces_secret_key
}
