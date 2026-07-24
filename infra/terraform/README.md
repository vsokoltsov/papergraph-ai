# PaperGraph AI GCP Infrastructure

This Terraform stack creates the GCP infrastructure needed to run PaperGraph AI:

- GKE Autopilot cluster for the API, migrations, MCP server, and monitoring.
- Cloud SQL PostgreSQL for feedback and agent run storage.
- Artifact Registry repository for container images.
- Regional static IP address for the public API load balancer.
- Google service account and IAM bindings for Workload Identity.
- GitHub Actions OIDC access to push images to Artifact Registry.
- GitHub Actions repository variables for image builds.

Production deployments should use managed Qdrant Cloud and Neo4j AuraDB endpoints. GCP does not
provide first-party managed Qdrant or Neo4j databases, so those learning/free tier instances are
created in the vendor consoles and passed to Helm.

## Usage

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Terraform uses the GitHub provider to create repository variables. Export a GitHub token before
planning/applying:

```bash
export GITHUB_TOKEN=...
```

The token needs repository access to `vsokoltsov/papergraph-ai` and repository **Variables**
read/write permission. Terraform reads existing variables during `plan` and creates/updates them
during `apply`.

Terraform manages infrastructure-derived GitHub Actions variables and Terraform-owned Secret
Manager values. Application/provider credentials that are not created by Terraform are stored in
Google Secret Manager. After Terraform creates the secret containers and IAM bindings, sync the
non-Terraform credentials from `.env`:

```bash
make sync-gcp-secrets
```

The CI deploy job reads Google Secret Manager values into temporary runner files and applies the
`papergraph-ai-secrets` Kubernetes Secret before Helm runs. It does not generate a values file with
interpolated secrets. If you deploy manually, GKE can also use External Secrets Operator to sync
Google Secret Manager values into Kubernetes.

The sync script uploads these keys:

- `OPENALEX_API_KEY`
- `OPENAI_API_KEY`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

Terraform writes these Secret Manager values directly from sensitive Terraform variables:

- `POSTGRES_PASSWORD`
- `LOGFIRE_API_KEY`

Terraform also writes these derived deployment values into GitHub Actions variables:

- `API_LOAD_BALANCER_IP`
- `GRAFANA_LOAD_BALANCER_IP`
- `GRAFANA_DASHBOARDS_BUCKET`
- `PAPERGRAPH_API_URL`
- `PAPERGRAPH_GRAFANA_URL`
- `QDRANT_URL`
- `NEO4J_URI`
- `POSTGRES_DATABASE`
- `POSTGRES_USER`
- `PROMETHEUS_PUSHGATEWAY_URL`
- `OTEL_SERVICE_NAME`
- `OTEL_TRACING_ENABLED`
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
- `LOGFIRE_ENABLED`

`PAPERGRAPH_API_URL` is derived from the reserved static IP and is used by CI to configure the
Cloud Run UI `API_URL` environment variable. Do not put this value in `.env`; before Terraform
applies, the production URL is not known.

`PAPERGRAPH_GRAFANA_URL` is derived from the reserved Grafana static IP. CI uses
`GRAFANA_LOAD_BALANCER_IP` to expose Grafana through a Kubernetes `LoadBalancer` service.

`GRAFANA_DASHBOARDS_BUCKET` points to the Terraform-managed GCS bucket used for generated Grafana
dashboard JSON. CI uploads generated dashboards to `gs://$GRAFANA_DASHBOARDS_BUCKET/dashboards`,
and the Grafana pod reads them with the GKE Workload Identity service account.

`QDRANT_URL` and `NEO4J_URI` are derived from the Helm-managed Kubernetes services:

- `http://papergraph-ai-qdrant:6333`
- `bolt://papergraph-ai-neo4j:7687`

They are GitHub Actions variables, not Terraform inputs and not Secret Manager values.

Before running the Helm deployment in CI, install External Secrets Operator in the GKE cluster as a
one-time platform bootstrap step. The Helm chart creates the `SecretStore` and `ExternalSecret`
resources, but the operator and CRDs are a cluster prerequisite. Install it with an operator/admin
identity, because the operator chart manages cluster-scoped RBAC and webhook resources.

The GitHub Actions deployment service account receives `roles/container.developer` so CI can fetch
GKE credentials and apply the Helm release after images are pushed. It also receives
`roles/run.admin` and `roles/iam.serviceAccountUser` so CI can deploy the Streamlit UI image to
Cloud Run using the application runtime service account.

Then configure kubectl:

The default Cloud SQL settings use the small learning tier:

```hcl
postgres_edition = "ENTERPRISE"
postgres_tier    = "db-f1-micro"
```

Do not use `db-f1-micro` with `ENTERPRISE_PLUS`; GCP only allows performance-optimized tiers for
that edition.

```bash
gcloud container clusters get-credentials papergraph-ai --region europe-west1 --project PROJECT_ID
```

Deploy the application with Helm:

```bash
helm upgrade --install papergraph-ai ../helm/papergraph \
  --namespace papergraph-ai \
  --create-namespace \
  --values ../helm/papergraph/values.yaml
```
