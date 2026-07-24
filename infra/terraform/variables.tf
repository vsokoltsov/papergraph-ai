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

variable "logfire_enabled" {
  description = "Whether deployed workloads should enable Logfire instrumentation."
  type        = bool
  default     = true
}

variable "logfire_api_key" {
  description = "Logfire write token. Stored in Secret Manager by Terraform when provided."
  type        = string
  sensitive   = true
  default     = ""
}

variable "otel_tracing_enabled" {
  description = "Whether deployed workloads should export OpenTelemetry traces."
  type        = bool
  default     = true
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
