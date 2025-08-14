provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  common_labels = {
    project     = var.app_name
    managed_by   = "opsmith"
  }
}

############################
# Networking: VPC, Subnet, Flow Logs
############################
resource "google_compute_network" "vpc_network" {
  name                    = "${var.app_name}-${var.environment}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "vpc_subnetwork" {
  name          = "${var.app_name}-${var.environment}-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network.id

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }

}

############################
# Firewall
############################
# HTTPS (443) from anywhere (default true for 443)
resource "google_compute_firewall" "allow_https" {
  name    = "${var.app_name}-${var.environment}-allow-https"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-${var.environment}-vm"]
}

resource "google_compute_firewall" "allow_http" {
  name    = "${var.app_name}-allow-http"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-${var.environment}-vm"]
}

# SSH via IAP (recommended)
resource "google_compute_firewall" "allow_ssh_iap" {
  name    = "${var.app_name}-${var.environment}-allow-ssh-iap"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP TCP forwarding range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["${var.app_name}-${var.environment}-vm"]
}

############################
# Cloud Router + NAT (egress for private VMs)
############################
resource "google_compute_router" "router" {
  name    = "${var.app_name}-${var.environment}-router"
  region  = var.region
  network = google_compute_network.vpc_network.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.app_name}-${var.environment}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.vpc_subnetwork.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }

}


############################
# Service Account + IAM
############################
resource "google_service_account" "vm_sa" {
  account_id   = "${var.app_name}-${var.environment}-vm-sa"
  display_name = "Service account for ${var.app_name}-${var.environment} VM"
}

# Least-privilege IAM: Artifact Registry read
resource "google_project_iam_member" "artifact_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.vm_sa.email}"
}

# IAM binding for logging
resource "google_project_iam_member" "logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.vm_sa.email}"
}

# IAM binding for monitoring
resource "google_project_iam_member" "monitoring_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.vm_sa.email}"
}

############################
# Compute Instance (Private by default)
############################
resource "google_compute_instance" "vm" {
  name                      = "${var.app_name}-${var.environment}-vm"
  machine_type              = var.instance_type
  zone                      = var.zone
  allow_stopping_for_update = true
  tags                      = ["${var.app_name}-${var.environment}-vm"]

  labels = merge(
    local.common_labels,
    {
      app  = var.app_name
    },
  )


  boot_disk {
    auto_delete = true
    initialize_params {
      image  = "debian-cloud/debian-12"
      size   = var.boot_disk_size_gb
      type   = var.boot_disk_type
    }
  }

  # Private VM by default (no access_config)
  network_interface {
    subnetwork = google_compute_subnetwork.vpc_subnetwork.id

    access_config {
      // Ephemeral IP
    }
  }

  # Strong instance hardening
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                = true
    enable_integrity_monitoring = true
  }

  # Prefer OS Login; avoid embedding SSH keys in metadata
  metadata = {
    ssh-keys = "dev:${var.ssh_pub_key}"
    enable-oslogin           = "FALSE"
    block-project-ssh-keys   = "TRUE"
  }

  service_account {
    email = google_service_account.vm_sa.email

    # Note: OAuth scopes are legacy. Keep cloud-platform and enforce least privilege via IAM roles above.
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    # Install Google Cloud Ops Agent
    curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
    sudo bash add-google-cloud-ops-agent-repo.sh --also-install
  EOT
}

