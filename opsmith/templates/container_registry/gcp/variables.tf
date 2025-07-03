variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "registry_name" {
  description = "The name for the Artifact Registry repository."
  type        = string
}

variable "region" {
  description = "The GCP region for the Artifact Registry repository."
  type        = string
}
