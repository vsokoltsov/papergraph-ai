variable "name" {
  description = "Base name for PaperGraph resources."
  type        = string
}

variable "region" {
  description = "GCP region for the reserved IP address."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}
