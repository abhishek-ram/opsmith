provider "google" {
  project = var.project_id
}

resource "google_compute_backend_bucket" "backend_bucket" {
  name        = "${var.app_name}-backend-bucket"
  description = "Backend bucket for ${var.app_name} frontend"
  bucket_name = var.bucket_name
  enable_cdn  = true

  cdn_policy {
    cache_mode                   = "CACHE_ALL_STATIC"
    default_ttl                 = 3600
    max_ttl                     = 86400
    client_ttl                  = 3600
    negative_caching            = true
    serve_while_stale           = 86400
  }
}

resource "google_compute_url_map" "url_map" {
  name            = "${var.app_name}-url-map"
  default_service = google_compute_backend_bucket.backend_bucket.id

  host_rule {
    hosts        = [var.domain_name, "www.${var.domain_name}"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_bucket.backend_bucket.id
  }

}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.app_name}-https-proxy"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [var.certificate_id]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name       = "${var.app_name}-forwarding-rule"
  target     = google_compute_target_https_proxy.https_proxy.id
  port_range = "443"
}
