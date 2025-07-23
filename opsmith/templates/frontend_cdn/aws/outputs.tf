output "cdn_domain_name" {
  description = "The domain name of the CloudFront distribution."
  value       = aws_cloudfront_distribution.s3_distribution.domain_name
}

output "cdn_distribution_id" {
  description = "The ID of the CloudFront distribution."
  value       = aws_cloudfront_distribution.s3_distribution.id
}

output "dns_records" {
  description = "DNS records to be configured."
  value = jsonencode([
    {
      type    = "CNAME",
      name    = var.domain_name,
      value   = aws_cloudfront_distribution.s3_distribution.domain_name,
      comment = "For Content Delivery Network"
    }
  ])
}
