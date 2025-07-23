provider "aws" {
  region = var.region
}

# Provider for us-east-1 (required for CloudFront certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_s3_bucket" "frontend_bucket" {
  bucket = var.domain_name
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_acm_certificate" "cert" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  provider = aws.us_east_1

  lifecycle {
    create_before_destroy = true
  }
}

