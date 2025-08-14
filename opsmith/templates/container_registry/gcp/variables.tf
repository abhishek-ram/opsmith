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

variable "force_delete" {
  description = "Force delete repository even if it contains images"
  type        = bool
  default     = false # Safer default
}