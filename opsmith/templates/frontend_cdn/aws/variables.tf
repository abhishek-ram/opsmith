variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "region" {
  description = "The AWS region."
  type        = string
}

variable "domain_name" {
  description = "The domain name for the website."
  type        = string
}

variable "bucket_name" {
  description = "The name of the S3 bucket."
  type        = string
}

variable "certificate_id" {
  description = "The ARN of the ACM certificate."
  type        = string
}

