resource "google_sql_database_instance" "postgres" {
  name             = "${var.name}-${var.environment}"
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    edition           = var.edition
    tier              = var.tier
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = true

  depends_on = [var.private_services_connection_id]
}

resource "google_sql_database" "app" {
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "app" {
  name     = var.database_user
  instance = google_sql_database_instance.postgres.name
  password = var.database_password
}
