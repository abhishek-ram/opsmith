output "public_ip" {
  description = "The public IP address of the GCE instance."
  value       = google_compute_instance.vm.network_interface[0].access_config[0].nat_ip
}

output "private_ip" {
  description = "The private IP address of the GCE instance."
  value       = google_compute_instance.vm.network_interface[0].network_ip
}

output "instance_id" {
  description = "The ID of the GCE instance."
  value       = google_compute_instance.vm.name
}

output "user" {
  description = "The user for Ansible to connect with."
  value       = "dev"
}
