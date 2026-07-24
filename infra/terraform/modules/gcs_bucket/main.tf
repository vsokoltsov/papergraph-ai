resource "google_storage_bucket" "main" {
  project                     = var.project_id
  name                        = var.name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  versioning {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "object_admin" {
  for_each = var.object_admin_members

  bucket = google_storage_bucket.main.name
  role   = "roles/storage.objectAdmin"
  member = each.value
}

resource "google_storage_bucket_iam_member" "object_viewer" {
  for_each = var.object_viewer_members

  bucket = google_storage_bucket.main.name
  role   = "roles/storage.objectViewer"
  member = each.value
}
