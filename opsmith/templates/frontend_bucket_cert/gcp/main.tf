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
