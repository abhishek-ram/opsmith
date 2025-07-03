output "registry_url" {
  description = "The URL of the ECR repository."
  value       = aws_ecr_repository.registry.repository_url
}
