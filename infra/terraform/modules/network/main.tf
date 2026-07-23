locals {
  labels = {
    app         = var.name
    environment = var.environment
  }
}

resource "google_compute_network" "main" {
  name                    = "${var.name}-${var.environment}"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "${var.name}-${var.environment}"
  ip_cidr_range = "10.20.0.0/20"
  network       = google_compute_network.main.id
  region        = var.region

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.24.0.0/14"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.28.0.0/20"
  }
}

resource "google_compute_global_address" "private_services" {
  name          = "${var.name}-${var.environment}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}
