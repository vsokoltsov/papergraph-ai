resource "google_compute_address" "api" {
  name         = "${var.name}-${var.environment}-api"
  address_type = "EXTERNAL"
  region       = var.region
}

resource "google_compute_address" "grafana" {
  name         = "${var.name}-${var.environment}-grafana"
  address_type = "EXTERNAL"
  region       = var.region
}
