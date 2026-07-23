output "variables" {
  description = "GitHub Actions variables managed by Terraform."
  value       = keys(github_actions_variable.managed)
}
