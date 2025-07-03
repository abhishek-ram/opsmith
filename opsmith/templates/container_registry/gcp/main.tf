provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "registry" {
  location      = var.region
  repository_id = var.registry_name
  description   = "Container registry for ${var.app_name}"
  format        = "DOCKER"
}
