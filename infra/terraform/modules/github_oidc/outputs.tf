output "provider_name" {
  description = "Full Workload Identity Provider resource name."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_email" {
  description = "GitHub Actions Google service account email."
  value       = google_service_account.github_actions.email
}

output "project_number" {
  description = "GCP project number."
  value       = data.google_project.current.number
}
