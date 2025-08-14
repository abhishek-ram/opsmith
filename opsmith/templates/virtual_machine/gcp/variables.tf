variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "environment" {
  description = "The name of the environment."
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

variable "zone" {
  description = "The GCP zone for the instance."
  type        = string
}

variable "instance_type" {
  description = "The GCE instance type."
  type        = string
}

variable "instance_arch" {
  description = "The architecture of the instance CPU."
  type        = string
}

variable "ssh_pub_key" {
  description = "The SSH public key for instance access."
  type        = string
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 20
}

variable "boot_disk_type" {
  description = "Boot disk type (pd-balanced, pd-ssd, pd-standard)"
  type        = string
  default     = "pd-balanced"
}