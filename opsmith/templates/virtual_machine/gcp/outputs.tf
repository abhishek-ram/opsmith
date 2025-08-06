output "instance_public_ip" {
  description = "The public IP address of the GCE instance."
  value       = google_compute_instance.app_server.network_interface[0].access_config[0].nat_ip
}

output "instance_id" {
  description = "The ID of the GCE instance."
  value       = google_compute_instance.app_server.instance_id
}

output "ansible_user" {
  description = "The user for Ansible to connect with."
  value       = "dev"
}
