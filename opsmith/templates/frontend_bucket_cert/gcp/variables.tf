variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "region" {
  description = "The GCP region."
  type        = string
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "domain_name" {
  description = "The domain name for the website."
  type        = string
}
