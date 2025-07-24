variable "app_name" {
  description = "The name of the application."
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

variable "bucket_name" {
  description = "The name of the GCS bucket."
  type        = string
}

variable "certificate_id" {
  description = "The ID of the managed SSL certificate."
  type        = string
}

variable "region" {
  description = "The GCP region."
  type        = string
}