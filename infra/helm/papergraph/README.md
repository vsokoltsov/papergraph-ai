# PaperGraph Helm Chart

This chart deploys:

- FastAPI backend to GKE.
- Alembic feedback migration as a Helm hook Job.
- Prometheus, Pushgateway, Tempo, and Grafana to GKE.
- Streamlit UI as a Cloud Run service through Config Connector.

Production defaults use managed Qdrant Cloud and Neo4j AuraDB endpoints. Use the learning/free tier
for each service when possible, then pass those endpoint values to Helm. In-cluster Qdrant and Neo4j
StatefulSets are available only through `values-dev.yaml`.

Production secrets are read from Google Secret Manager:

- GKE workloads use External Secrets Operator to sync Google Secret Manager values into the
  `papergraph-ai-secrets` Kubernetes Secret.
- The Cloud Run UI reads `PAPERGRAPH_API_URL` directly from Google Secret Manager through Config
  Connector.

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
`gcloud run deploy`.

```bash
helm upgrade --install papergraph-ai infra/helm/papergraph \
  --namespace papergraph-ai \
  --create-namespace \
  --set serviceAccount.gcpServiceAccount=papergraph-ai@PROJECT_ID.iam.gserviceaccount.com \
  --set images.api=europe-west1-docker.pkg.dev/PROJECT_ID/papergraph-ai-prod/api:latest \
  --set images.ui=europe-west1-docker.pkg.dev/PROJECT_ID/papergraph-ai-prod/ui:latest \
  --set externalSecrets.projectId=PROJECT_ID \
  --set external.postgresHost=CLOUD_SQL_PRIVATE_IP
```

For a self-contained development/staging deployment, use in-cluster Qdrant and Neo4j:

```bash
helm upgrade --install papergraph-ai infra/helm/papergraph \
  --namespace papergraph-ai \
  --create-namespace \
  --values infra/helm/papergraph/values-dev.yaml
```
