output "secret_ids" {
  description = "Created Secret Manager secret IDs."
  value       = keys(google_secret_manager_secret.managed)
}
