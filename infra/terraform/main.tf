module "project_services" {
  source     = "./modules/project_services"
  project_id = var.project_id
}

module "network" {
  source      = "./modules/network"
  name        = var.name
  region      = var.region
  environment = var.environment

  depends_on = [module.project_services]
}

module "artifact_registry" {
  source      = "./modules/artifact_registry"
  name        = var.name
  region      = var.region
  environment = var.environment

  depends_on = [module.project_services]
}

module "gke" {
  source      = "./modules/gke"
  project_id  = var.project_id
  name        = var.name
  region      = var.region
  network_id  = module.network.network_id
  subnet_id   = module.network.subnet_id
  environment = var.environment

  depends_on = [module.project_services]
}

module "cloud_sql" {
  source                         = "./modules/cloud_sql"
  name                           = var.name
  region                         = var.region
  network_id                     = module.network.network_id
  private_services_connection_id = module.network.private_services_connection_id
  database_name                  = var.postgres_database
  database_user                  = var.postgres_user
  database_password              = var.postgres_password
  edition                        = var.postgres_edition
  tier                           = var.postgres_tier
  environment                    = var.environment

  depends_on = [module.project_services, module.network]
}

module "workload_identity" {
  source        = "./modules/workload_identity"
  project_id    = var.project_id
  name          = var.name
  namespace     = var.name
  ksa_name      = var.name
  gke_namespace = module.gke.workload_identity_namespace

  depends_on = [module.gke]
}

module "github_oidc" {
  source            = "./modules/github_oidc"
  project_id        = var.project_id
  name              = var.name
  environment       = var.environment
  github_owner      = var.github_owner
  github_repository = var.github_repository

  depends_on = [module.project_services]
}

module "secret_manager" {
  source     = "./modules/secret_manager"
  project_id = var.project_id
  secret_ids = toset([
    "OPENALEX_API_KEY",
    "OPENAI_API_KEY",
    "QDRANT_URL",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "POSTGRES_PASSWORD",
    "PAPERGRAPH_API_URL",
    "LOGFIRE_TOKEN",
  ])
  accessor_service_accounts = toset([
    module.workload_identity.service_account_email,
  ])

  depends_on = [module.project_services, module.workload_identity]
}

module "github_actions" {
  source     = "./modules/github_actions"
  repository = var.github_repository
  variables = {
    GCP_PROJECT_ID                 = var.project_id
    GCP_REGION                     = var.region
    GAR_HOST                       = "${var.region}-docker.pkg.dev"
    GAR_REPOSITORY                 = module.artifact_registry.repository_id
    ARTIFACT_REGISTRY_URL          = module.artifact_registry.repository_url
    GCP_WORKLOAD_IDENTITY_PROVIDER = module.github_oidc.provider_name
    GCP_SERVICE_ACCOUNT            = module.github_oidc.service_account_email
    GKE_CLUSTER_NAME               = module.gke.cluster_name
    GKE_CLUSTER_REGION             = module.gke.cluster_region
    HELM_RELEASE                   = var.name
    HELM_NAMESPACE                 = var.name
    GKE_WORKLOAD_SERVICE_ACCOUNT   = module.workload_identity.service_account_email
    CLOUD_SQL_PRIVATE_IP           = module.cloud_sql.private_ip_address
    SECRET_MANAGER_PROJECT_ID      = var.project_id
    CLOUD_RUN_UI_SERVICE_NAME      = "${var.name}-ui"
  }

  depends_on = [module.github_oidc, module.artifact_registry, module.secret_manager]
}
