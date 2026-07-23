variable "name" {
  description = "Base resource name."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
}

variable "network_id" {
  description = "VPC network ID."
  type        = string
}

variable "private_services_connection_id" {
  description = "Private services VPC peering connection ID."
  type        = string
}

variable "database_name" {
  description = "Database name."
  type        = string
}

variable "database_user" {
  description = "Database user."
  type        = string
}

variable "database_password" {
  description = "Database password."
  type        = string
  sensitive   = true
}

variable "edition" {
  description = "Cloud SQL edition. ENTERPRISE supports small shared-core learning tiers."
  type        = string
  default     = "ENTERPRISE"
}

variable "tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-f1-micro"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}
