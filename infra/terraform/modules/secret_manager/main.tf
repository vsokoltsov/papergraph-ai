resource "google_secret_manager_secret" "managed" {
  for_each = var.secret_ids

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = {
    for pair in setproduct(var.secret_ids, var.accessor_service_accounts) :
    "${pair[0]}:${pair[1]}" => {
      secret_id             = pair[0]
      service_account_email = pair[1]
    }
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.managed[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.service_account_email}"
}
