provider "google" {
  project = var.project_id
}

resource "google_storage_bucket" "frontend_bucket" {
  name          = var.domain_name
  location      = "US" # Cloud storage buckets are multi-regional
  force_destroy = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }
}

resource "google_storage_bucket_iam_member" "public_reader" {
  bucket = google_storage_bucket.frontend_bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  name    = "${var.app_name}-ssl-cert"
  managed {
    domains = [var.domain_name]
  }
}

resource "google_compute_backend_bucket" "backend_bucket" {
  name        = "${var.app_name}-backend-bucket"
  description = "Backend bucket for ${var.app_name} frontend"
  bucket_name = google_storage_bucket.frontend_bucket.name
  enable_cdn  = true
}

resource "google_compute_url_map" "url_map" {
  name            = "${var.app_name}-url-map"
  default_service = google_compute_backend_bucket.backend_bucket.id
}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.app_name}-https-proxy"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.ssl_cert.id]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name       = "${var.app_name}-forwarding-rule"
  target     = google_compute_target_https_proxy.https_proxy.id
  port_range = "443"
}
