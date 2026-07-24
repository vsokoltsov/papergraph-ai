# PaperGraph Helm Chart

This chart deploys:

- FastAPI backend to GKE.
- Alembic feedback migration as a Helm hook Job.
- Prometheus, Pushgateway, Tempo, and Grafana to GKE.
- Streamlit UI as an optional Cloud Run service through Config Connector.

Production defaults use managed Qdrant Cloud and Neo4j AuraDB endpoints. Use the learning/free tier
for each service when possible, then pass those endpoint values to Helm. In-cluster Qdrant and Neo4j
StatefulSets are available only through `values-dev.yaml`.

Production credentials are read from Google Secret Manager. Infrastructure-derived URLs and
runtime flags are not stored as secrets; CI passes them to Helm from GitHub Actions variables
created by Terraform:

- GKE workloads use External Secrets Operator to sync Google Secret Manager values into the
  `papergraph-ai-secrets` Kubernetes Secret.
- Terraform reserves a static API load balancer IP and stores the derived API URL in the
  `PAPERGRAPH_API_URL` GitHub Actions variable. CI passes that value directly to Cloud Run as the
  UI runtime `API_URL`; it is not stored in `.env` or Google Secret Manager.
- Terraform also provides the Helm-derived Qdrant URL, Neo4j URI, Postgres user/database,
  Pushgateway URL, and OTEL settings consumed by the Helm chart.

The CI deployment path does not require External Secrets Operator. It reads Google Secret Manager
values into a temporary runner directory and applies the `papergraph-ai-secrets` Kubernetes Secret
before Helm runs, with `externalSecrets.enabled=false` and `secrets.create=false`.

Before deploying the production chart, install External Secrets Operator in the GKE cluster as a
one-time platform bootstrap step. The chart creates a `SecretStore` and `ExternalSecret`, but the
CRDs and controller must already exist. Do this with an operator/admin identity, not with the
application deployment service account:

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --set installCRDs=true \
  --wait
```

Before enabling `cloudRunUi`, install and configure Config Connector in the GKE cluster. If Config
Connector is not installed, set `cloudRunUi.enabled=false` and deploy the UI with Terraform or
`gcloud run deploy`. The CI pipeline uses this second approach: Helm deploys the GKE resources with
`cloudRunUi.enabled=false`, then `gcloud run deploy` updates the Cloud Run UI service.

```bash
helm upgrade --install papergraph-ai infra/helm/papergraph \
  --namespace papergraph-ai \
  --create-namespace \
  --set serviceAccount.gcpServiceAccount=papergraph-ai@PROJECT_ID.iam.gserviceaccount.com \
  --set images.api=europe-west1-docker.pkg.dev/PROJECT_ID/papergraph-ai-prod/api:latest \
  --set images.ui=europe-west1-docker.pkg.dev/PROJECT_ID/papergraph-ai-prod/ui:latest \
  --set externalSecrets.projectId=PROJECT_ID \
  --set external.postgresHost=CLOUD_SQL_PRIVATE_IP \
  --set api.serviceType=LoadBalancer \
  --set api.loadBalancerIP=API_LOAD_BALANCER_IP \
  --set external.apiUrl=http://API_LOAD_BALANCER_IP:8000
```

For a self-contained development/staging deployment, use in-cluster Qdrant and Neo4j:

```bash
helm upgrade --install papergraph-ai infra/helm/papergraph \
  --namespace papergraph-ai \
  --create-namespace \
  --values infra/helm/papergraph/values-dev.yaml
```
