resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "${var.name}-${var.environment}"
  description   = "PaperGraph AI container images"
  format        = "DOCKER"
}
