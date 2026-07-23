output "artifact_registry_repository" {
  description = "Docker Artifact Registry repository."
  value       = module.artifact_registry.repository_name
}

output "artifact_registry_url" {
  description = "Docker Artifact Registry URL prefix."
  value       = module.artifact_registry.repository_url
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name."
  value       = module.cloud_sql.connection_name
}

output "gke_cluster_name" {
  description = "GKE cluster name."
  value       = module.gke.cluster_name
}

output "gke_cluster_region" {
  description = "GKE cluster region."
  value       = module.gke.cluster_region
}

output "workload_identity_service_account" {
  description = "Google service account used by PaperGraph workloads."
  value       = module.workload_identity.service_account_email
}

output "github_actions_service_account" {
  description = "Google service account used by GitHub Actions."
  value       = module.github_oidc.service_account_email
}

output "github_actions_workload_identity_provider" {
  description = "Workload Identity Provider name for GitHub Actions."
  value       = module.github_oidc.provider_name
}
