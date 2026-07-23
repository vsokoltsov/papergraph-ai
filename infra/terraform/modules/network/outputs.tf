output "network_id" {
  description = "VPC network ID."
  value       = google_compute_network.main.id
}

output "subnet_id" {
  description = "Subnet ID."
  value       = google_compute_subnetwork.main.id
}

output "private_services_connection_id" {
  description = "Private services VPC peering connection ID."
  value       = google_service_networking_connection.private_services.id
}
