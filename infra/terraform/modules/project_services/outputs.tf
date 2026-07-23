output "services" {
  description = "Enabled GCP services."
  value       = [for service in google_project_service.enabled : service.service]
}
