output "bucket_name" {
  description = "The name of the S3 bucket."
  value       = aws_s3_bucket.frontend_bucket.id
}

output "cdn_domain_name" {
  description = "The domain name of the CloudFront distribution."
  value       = aws_cloudfront_distribution.s3_distribution.domain_name
}

output "dns_records" {
  description = "DNS records to be configured."
  value = jsonencode([
    {
      type    = "CNAME",
      name    = one(aws_acm_certificate.cert.domain_validation_options).resource_record_name,
      value   = one(aws_acm_certificate.cert.domain_validation_options).resource_record_value,
      comment = "For SSL Certificate Validation"
    },
    {
      type    = "CNAME",
      name    = var.domain_name,
      value   = aws_cloudfront_distribution.s3_distribution.domain_name,
      comment = "For Content Delivery Network"
    }
  ])
}
