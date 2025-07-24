output "bucket_name" {
  description = "The name of the S3 bucket."
  value       = aws_s3_bucket.frontend_bucket.id
}

output "certificate_id" {
  description = "The ARN of the ACM certificate."
  value       = aws_acm_certificate.cert.arn
}

output "dns_records" {
  description = "DNS records to be configured for SSL certificate validation."
  value = jsonencode([
    {
      type    = "CNAME",
      name    = one(aws_acm_certificate.cert.domain_validation_options).resource_record_name,
      value   = one(aws_acm_certificate.cert.domain_validation_options).resource_record_value,
      comment = "For SSL Certificate Validation"
    }
  ])
}
