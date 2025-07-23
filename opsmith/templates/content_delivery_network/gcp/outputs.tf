output "bucket_name" {
  description = "The name of the GCS bucket."
  value       = google_storage_bucket.frontend_bucket.name
}

output "cdn_ip_address" {
  description = "The IP address of the CDN/Load Balancer."
  value       = google_compute_global_forwarding_rule.forwarding_rule.ip_address
}

output "dns_records" {
  description = "DNS records to be configured."
  value = jsonencode([
    {
      type    = "A",
      name    = var.domain_name,
      value   = google_compute_global_forwarding_rule.forwarding_rule.ip_address,
      comment = "For Content Delivery Network"
    }
  ])
}
