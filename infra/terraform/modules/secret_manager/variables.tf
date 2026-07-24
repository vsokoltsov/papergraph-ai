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

variable "secret_values" {
  description = "Secret values to write as Secret Manager versions."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "managed_secret_value_ids" {
  description = "Secret IDs that should receive Terraform-managed secret versions."
  type        = set(string)
  default     = []
}
