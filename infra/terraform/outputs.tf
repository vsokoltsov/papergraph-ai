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

output "cloud_sql_private_ip_address" {
  description = "Cloud SQL private IP address."
  value       = module.cloud_sql.private_ip_address
}

output "gke_cluster_name" {
  description = "GKE cluster name."
  value       = module.gke.cluster_name
}

output "gke_cluster_region" {
  description = "GKE cluster region."
  value       = module.gke.cluster_region
}

output "api_load_balancer_ip" {
  description = "Reserved external IP address for the PaperGraph API load balancer."
  value       = module.static_ip.api_ip_address
}

output "papergraph_api_url" {
  description = "HTTP URL for the PaperGraph API load balancer."
  value       = module.static_ip.api_url
}

output "cloud_run_ui_url" {
  description = "Expected Cloud Run URL for the Streamlit UI service deployed by CI."
  value       = "https://${var.name}-ui-${data.google_project.current.number}.${var.region}.run.app"
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

output "secret_manager_secret_ids" {
  description = "Secret Manager secret IDs managed by Terraform."
  value       = module.secret_manager.secret_ids
}
