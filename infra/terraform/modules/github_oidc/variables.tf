variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "name" {
  description = "Base resource name."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "github_owner" {
  description = "GitHub repository owner."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository name."
  type        = string
}
