variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "region" {
  description = "The AWS region."
  type        = string
}

variable "instance_type" {
  description = "The EC2 instance type."
  type        = string
}

variable "ssh_pub_key" {
  description = "The SSH public key for instance access."
  type        = string
}
