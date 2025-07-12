variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "region" {
  description = "The GCP region for the instance."
  type        = string
}

variable "instance_type" {
  description = "The GCE instance type."
  type        = string
}

variable "ssh_pub_key" {
  description = "The SSH public key for instance access."
  type        = string
}
