resource "google_container_cluster" "main" {
  name             = "${var.name}-${var.environment}"
  location         = var.region
  enable_autopilot = true
  network          = var.network_id
  subnetwork       = var.subnet_id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  deletion_protection = true
}
