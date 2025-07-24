output "bucket_name" {
  description = "The name of the GCS bucket."
  value       = google_storage_bucket.frontend_bucket.name
}

output "certificate_id" {
  description = "The self_link of the managed SSL certificate."
  value       = google_compute_managed_ssl_certificate.ssl_cert.self_link
}

