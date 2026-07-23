output "connection_name" {
  description = "Cloud SQL connection name."
  value       = google_sql_database_instance.postgres.connection_name
}

output "private_ip_address" {
  description = "Cloud SQL private IP address."
  value       = google_sql_database_instance.postgres.private_ip_address
}
