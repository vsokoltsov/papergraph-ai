variable "repository" {
  description = "GitHub repository name."
  type        = string
}

variable "variables" {
  description = "GitHub Actions repository variables."
  type        = map(string)
}
