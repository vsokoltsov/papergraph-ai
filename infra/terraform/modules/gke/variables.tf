variable "project_id" {
  description = "GCP project ID."
  type        = string
}

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

variable "subnet_id" {
  description = "Subnet ID."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}
