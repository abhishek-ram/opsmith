variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "registry_name" {
  description = "The name for the ECR repository."
  type        = string
}

variable "region" {
  description = "The AWS region for the ECR repository."
  type        = string
}
