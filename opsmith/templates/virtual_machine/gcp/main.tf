provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_network" "vpc_network" {
  project                 = var.project_id
  name                    = "${var.app_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "vpc_subnetwork" {
  project                  = var.project_id
  name                     = "${var.app_name}-subnet"
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc_network.id
  private_ip_google_access = true
}

resource "google_compute_firewall" "allow_traffic" {
  name    = "${var.app_name}-allow-traffic"
  network = google_compute_network.vpc_network.name
  allow {
    protocol = "tcp"
    ports    = ["22", "80"]
  }
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-monolithic-server"]
}

resource "google_compute_instance" "app_server" {
  project      = var.project_id
  name         = "${var.app_name}-monolithic-server"
  machine_type = var.instance_type
  zone         = "${var.region}-a" # Simple assumption for zone

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpc_subnetwork.id
    access_config {
      // Ephemeral IP
    }
  }

  metadata = {
    ssh-keys = "dev:${var.ssh_pub_key}"
  }

  tags = ["${var.app_name}-monolithic-server"]

  service_account {
    scopes = ["cloud-platform"]
  }
}
