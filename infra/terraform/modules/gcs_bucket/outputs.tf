output "bucket_name" {
  description = "Storage bucket name."
  value       = google_storage_bucket.main.name
}
