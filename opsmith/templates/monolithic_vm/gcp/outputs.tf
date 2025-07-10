output "instance_public_ip" {
  description = "The public IP address of the GCE instance."
  value       = google_compute_instance.app_server.network_interface[0].access_config[0].nat_ip
}

output "instance_name" {
  description = "The name of the GCE instance."
  value       = google_compute_instance.app_server.name
}
