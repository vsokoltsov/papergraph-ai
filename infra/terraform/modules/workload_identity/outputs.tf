output "service_account_email" {
  description = "Google service account email."
  value       = google_service_account.app.email
}
