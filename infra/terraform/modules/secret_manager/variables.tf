variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "secret_ids" {
  description = "Secret Manager secret IDs to create."
  type        = set(string)
}

variable "accessor_service_accounts" {
  description = "Service account emails that can access secret versions."
  type        = set(string)
}
