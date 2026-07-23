resource "github_actions_variable" "managed" {
  for_each = var.variables

  repository    = var.repository
  variable_name = each.key
  value         = each.value
}
