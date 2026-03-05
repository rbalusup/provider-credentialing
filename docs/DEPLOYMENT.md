# Deployment Guide

This project ships with automated CI/CD via GitHub Actions. Two deployment targets are supported:

| Target | Workflow | Compute | Container registry |
|--------|----------|---------|-------------------|
| **AWS** | `deploy-aws.yml` | ECS Fargate | Amazon ECR |
| **GCP** | `deploy-gcp.yml` | Cloud Run | Artifact Registry |

Both workflows trigger on a Git tag push (`v*.*.*`) or can be run manually from the GitHub Actions UI.

---

## Quick Release

```bash
# After all tests pass on main:
git tag v1.0.0
git push origin v1.0.0
# → Both deploy-aws and deploy-gcp workflows start automatically
```

---

## Prerequisites (one-time setup)

### 1. GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**.

#### For AWS

| Secret | How to get it |
|--------|--------------|
| `AWS_ACCESS_KEY_ID` | IAM → Users → your user → Security credentials → Create access key |
| `AWS_SECRET_ACCESS_KEY` | Same as above (shown once at creation) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |

The IAM user needs these AWS permissions:
- `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:BatchCheckLayerAvailability`
- `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`, `ecs:UpdateService`, `ecs:DescribeServices`
- `iam:PassRole` (to pass the ECS task execution role)

#### For GCP

| Secret | How to get it |
|--------|--------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | See WIF setup below |
| `GCP_SERVICE_ACCOUNT` | Service account email (e.g. `deployer@my-project.iam.gserviceaccount.com`) |

> The GCP workflow uses **Workload Identity Federation** — no JSON key file stored in GitHub. This is the Google-recommended approach.

---

## AWS Setup

### Step 1 — Create an ECR repository

```bash
aws ecr create-repository \
    --repository-name provider-credentialing \
    --region us-east-1
```

Note the URI: `<account_id>.dkr.ecr.us-east-1.amazonaws.com/provider-credentialing`

### Step 2 — Create an ECS cluster

```bash
aws ecs create-cluster \
    --cluster-name provider-credentialing-cluster \
    --region us-east-1
```

### Step 3 — Create a task execution role

```bash
# Create the role
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document '{
        "Version":"2012-10-17",
        "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }'

# Attach the managed policy
aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### Step 4 — Register an initial task definition

Save this as `task-definition-init.json` (replace `<account_id>` and `<region>`):

```json
{
  "family": "provider-credentialing",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<account_id>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "provider-credentialing",
      "image": "<account_id>.dkr.ecr.<region>.amazonaws.com/provider-credentialing:latest",
      "essential": true,
      "environment": [
        {"name": "LOG_FORMAT", "value": "json"},
        {"name": "ENVIRONMENT", "value": "staging"}
      ],
      "secrets": [
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:<region>:<account_id>:secret:anthropic-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/provider-credentialing",
          "awslogs-region": "<region>",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

```bash
aws ecs register-task-definition \
    --cli-input-json file://task-definition-init.json
```

### Step 5 — Create an ECS service

```bash
aws ecs create-service \
    --cluster provider-credentialing-cluster \
    --service-name provider-credentialing-service \
    --task-definition provider-credentialing \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### Step 6 — Update workflow variables

In `.github/workflows/deploy-aws.yml`, set the `env:` block at the top:

```yaml
env:
  AWS_REGION: us-east-1                       # your region
  ECR_REPOSITORY: provider-credentialing
  ECS_CLUSTER: provider-credentialing-cluster
  ECS_SERVICE: provider-credentialing-service
  ECS_TASK_FAMILY: provider-credentialing
  CONTAINER_NAME: provider-credentialing
```

### Step 7 — Store the API key in Secrets Manager (recommended)

```bash
aws secretsmanager create-secret \
    --name anthropic-api-key \
    --secret-string "sk-ant-your-real-key-here" \
    --region us-east-1
```

Then reference it in the task definition `secrets` array (as shown in step 4) instead of passing it as a plain environment variable.

---

## GCP Setup

### Step 1 — Enable required APIs

```bash
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com
```

### Step 2 — Create an Artifact Registry repository

```bash
gcloud artifacts repositories create provider-credentialing \
    --repository-format=docker \
    --location=us-central1 \
    --description="Provider credentialing Docker images"
```

### Step 3 — Create a deployer service account

```bash
gcloud iam service-accounts create deployer \
    --display-name="GitHub Actions deployer"

export SA_EMAIL="deployer@$(gcloud config get-value project).iam.gserviceaccount.com"

# Grant permissions
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 4 — Configure Workload Identity Federation

This lets GitHub Actions authenticate to GCP without storing any JSON key file.

```bash
export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"
export REPO="rbalusup/provider-credentialing"

# Create the pool
gcloud iam workload-identity-pools create $POOL_ID \
    --location="global" \
    --display-name="GitHub Actions pool"

# Create the provider
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
    --location="global" \
    --workload-identity-pool=$POOL_ID \
    --display-name="GitHub provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com"

# Allow the GitHub repo to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$REPO"

# Print the values to store as GitHub secrets
echo "GCP_WORKLOAD_IDENTITY_PROVIDER:"
echo "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/providers/$PROVIDER_ID"
echo ""
echo "GCP_SERVICE_ACCOUNT: $SA_EMAIL"
```

Store the two printed values as GitHub secrets.

### Step 5 — Store the API key in Secret Manager

```bash
echo -n "sk-ant-your-real-key-here" | \
    gcloud secrets create anthropic-api-key \
        --data-file=- \
        --replication-policy=automatic
```

### Step 6 — Update workflow variables

In `.github/workflows/deploy-gcp.yml`:

```yaml
env:
  GCP_REGION: us-central1
  GCP_PROJECT_ID: your-actual-project-id
  AR_REPOSITORY: provider-credentialing
  IMAGE_NAME: provider-credentialing
  CLOUD_RUN_SERVICE: provider-credentialing
```

---

## Environments (staging vs production)

Both workflows accept a manual `environment` input (`staging` or `production`). When triggered by a tag push, `staging` is used by default.

To add a `production` deployment gate in GitHub:

1. Go to **Settings → Environments → New environment** → name it `production`
2. Add **Required reviewers** — a team member must approve before the workflow proceeds
3. Push tag → workflow runs → pauses at the deploy step waiting for approval

---

## Verifying a Deployment

### AWS

```bash
# Check ECS service status
aws ecs describe-services \
    --cluster provider-credentialing-cluster \
    --services provider-credentialing-service \
    --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'

# View recent task logs
aws logs tail /ecs/provider-credentialing --follow
```

### GCP

```bash
# Cloud Run service details
gcloud run services describe provider-credentialing \
    --region us-central1 \
    --format="value(status.url)"

# Recent logs
gcloud logging read \
    'resource.type=cloud_run_revision AND resource.labels.service_name=provider-credentialing' \
    --limit=50 \
    --format="value(textPayload)"
```

---

## Rolling Back

### AWS

```bash
# List recent task definitions
aws ecs list-task-definitions --family-prefix provider-credentialing

# Roll back the service to a previous revision
aws ecs update-service \
    --cluster provider-credentialing-cluster \
    --service provider-credentialing-service \
    --task-definition provider-credentialing:PREVIOUS_REVISION_NUMBER
```

### GCP

```bash
# List recent revisions
gcloud run revisions list --service provider-credentialing --region us-central1

# Route all traffic to a specific previous revision
gcloud run services update-traffic provider-credentialing \
    --region us-central1 \
    --to-revisions=REVISION_NAME=100
```

---

## Cost Notes

| Service | Billing model | Estimated cost (low volume) |
|---------|--------------|----------------------------|
| AWS ECS Fargate | per vCPU/memory-hour | ~$15–30/month for 0.5 vCPU / 1 GB always-on |
| AWS ECR | per GB stored + data transfer | < $1/month for typical image sizes |
| GCP Cloud Run | per request + CPU/memory while active | $0 at low volume (generous free tier) |
| GCP Artifact Registry | per GB stored | ~$0.10/GB/month |

Cloud Run's scale-to-zero means **$0 when idle**, making it the cheaper option for low-volume or batch workloads.