output "cluster_name" {
  description = "GKE cluster name."
  value       = google_container_cluster.main.name
}

output "cluster_region" {
  description = "GKE cluster region."
  value       = google_container_cluster.main.location
}

output "workload_identity_namespace" {
  description = "GKE Workload Identity namespace."
  value       = google_container_cluster.main.workload_identity_config[0].workload_pool
}
