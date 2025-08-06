provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "artifactregistry" {
  service = "artifactregistry.googleapis.com"

  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_artifact_registry_repository" "registry" {
  depends_on = [google_project_service.artifactregistry]

  location      = var.region
  repository_id = var.registry_name
  description   = "Container registry for ${var.app_name}"
  format        = "DOCKER"

  labels = {
    application = var.app_name
    managed_by  = "terraform"
  }
}
