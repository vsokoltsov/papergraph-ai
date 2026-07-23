output "repository_name" {
  description = "Artifact Registry repository name."
  value       = google_artifact_registry_repository.docker.name
}

output "repository_id" {
  description = "Artifact Registry repository ID."
  value       = google_artifact_registry_repository.docker.repository_id
}

output "repository_url" {
  description = "Docker repository URL prefix."
  value       = "${var.region}-docker.pkg.dev/${google_artifact_registry_repository.docker.project}/${google_artifact_registry_repository.docker.repository_id}"
}
