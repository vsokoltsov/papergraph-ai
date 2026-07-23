variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Primary GCP region."
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "prod"
}

variable "name" {
  description = "Base name for PaperGraph resources."
  type        = string
  default     = "papergraph-ai"
}

variable "postgres_database" {
  description = "Cloud SQL database name."
  type        = string
  default     = "papergraph"
}

variable "postgres_user" {
  description = "Cloud SQL application user."
  type        = string
  default     = "papergraph"
}

variable "postgres_password" {
  description = "Cloud SQL application password."
  type        = string
  sensitive   = true
}

variable "postgres_edition" {
  description = "Cloud SQL edition. Use ENTERPRISE for learning tier instances."
  type        = string
  default     = "ENTERPRISE"
}

variable "postgres_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-f1-micro"
}

variable "github_owner" {
  description = "GitHub repository owner."
  type        = string
  default     = "vsokoltsov"
}

variable "github_repository" {
  description = "GitHub repository name."
  type        = string
  default     = "papergraph-ai"
}
