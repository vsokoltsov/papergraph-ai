variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "name" {
  description = "Base resource name."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace."
  type        = string
}

variable "ksa_name" {
  description = "Kubernetes service account name."
  type        = string
}

variable "gke_namespace" {
  description = "GKE Workload Identity namespace."
  type        = string
}
