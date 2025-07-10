provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.app_name}-allow-ssh"
  network = "default"
  allow {
    protocol = "tcp"
    ports    = ["22"]
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
    network = "default"
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
