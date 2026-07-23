# PaperGraph AI GCP Infrastructure

This Terraform stack creates the GCP infrastructure needed to run PaperGraph AI:

- GKE Autopilot cluster for the API, migrations, MCP server, and monitoring.
- Cloud SQL PostgreSQL for feedback and agent run storage.
- Artifact Registry repository for container images.
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

The token needs permission to manage repository Actions variables.

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
