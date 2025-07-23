output "cdn_ip_address" {
  description = "The IP address of the CDN/Load Balancer."
  value       = google_compute_global_forwarding_rule.forwarding_rule.ip_address
}

output "cdn_url_map" {
  description = "The name of the URL map for the CDN."
  value       = basename(google_compute_target_https_proxy.https_proxy.url_map)
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
