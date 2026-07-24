variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "name" {
  description = "Storage bucket name."
  type        = string
}

variable "region" {
  description = "Storage bucket location."
  type        = string
}

variable "object_admin_members" {
  description = "IAM members that can write dashboard objects."
  type        = set(string)
  default     = []
}

variable "object_viewer_members" {
  description = "IAM members that can read dashboard objects."
  type        = set(string)
  default     = []
}
