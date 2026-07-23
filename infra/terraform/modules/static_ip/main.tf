resource "google_compute_address" "api" {
  name         = "${var.name}-${var.environment}-api"
  address_type = "EXTERNAL"
  region       = var.region
}
