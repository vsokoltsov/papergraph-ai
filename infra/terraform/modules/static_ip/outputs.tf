output "api_ip_address" {
  description = "Reserved external IP address for the PaperGraph API load balancer."
  value       = google_compute_address.api.address
}

output "api_url" {
  description = "HTTP URL for the PaperGraph API load balancer."
  value       = "http://${google_compute_address.api.address}:8000"
}

output "grafana_ip_address" {
  description = "Reserved external IP address for the PaperGraph Grafana load balancer."
  value       = google_compute_address.grafana.address
}

output "grafana_url" {
  description = "HTTP URL for the PaperGraph Grafana load balancer."
  value       = "http://${google_compute_address.grafana.address}:3000"
}
