output "registry_url" {
  description = "The URL of the Artifact Registry repository."
  value       = "${google_artifact_registry_repository.registry.location}-docker.pkg.dev/${google_artifact_registry_repository.registry.project}/${google_artifact_registry_repository.registry.repository_id}"
}
