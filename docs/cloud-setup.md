# Cloud & HPC Backend Setup Guide

This guide covers setting up BioAgent's cloud execution backends for running compute-intensive bioinformatics workloads at scale.

## Table of Contents

1. [Overview](#overview)
2. [AWS Batch Setup](#aws-batch-setup)
3. [Google Cloud Life Sciences Setup](#google-cloud-life-sciences-setup)
4. [Azure Batch Setup](#azure-batch-setup)
5. [SLURM HPC Setup](#slurm-hpc-setup)
6. [Environment Variables Reference](#environment-variables-reference)
7. [Testing Your Setup](#testing-your-setup)
8. [Troubleshooting](#troubleshooting)

---

## Overview

BioAgent supports four execution backends:

| Backend | Best For | Cost Model |
|---------|----------|------------|
| AWS Batch | Large-scale cloud workloads | Pay-per-use, Spot instances |
| GCP Life Sciences | Genomics pipelines | Pay-per-use, Preemptible VMs |
| Azure Batch | Enterprise environments | Pay-per-use, Low-priority VMs |
| SLURM | On-premise HPC clusters | Institutional allocation |

### Prerequisites

- Python 3.10+ with BioAgent installed
- Cloud provider account with billing enabled (for cloud backends)
- SSH access to cluster (for SLURM)

### Quick Start

Set environment variables for your chosen backend, then BioAgent automatically detects and uses it:

```bash
# Example: Enable AWS Batch
export AWS_S3_BUCKET="my-bioagent-bucket"
export AWS_BATCH_QUEUE="bioagent-queue"

# Verify
python -c "from cloud import CloudConfig; c = CloudConfig.from_env(); print('AWS:', c.is_aws_configured())"
```

---

## AWS Batch Setup

AWS Batch manages compute resources automatically, scaling up for jobs and down when idle.

### Step 1: Install AWS CLI and SDK

```bash
pip install boto3 awscli
aws configure  # Enter your AWS credentials
```

### Step 2: Create S3 Bucket for Data

```bash
# Create bucket for inputs/outputs
aws s3 mb s3://my-bioagent-data --region us-east-1

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
    --bucket my-bioagent-data \
    --versioning-configuration Status=Enabled
```

### Step 3: Create IAM Role for Batch Jobs

Create `batch-role-policy.json`:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::my-bioagent-data",
                "arn:aws:s3:::my-bioagent-data/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

```bash
# Create role
aws iam create-role \
    --role-name BioAgentBatchRole \
    --assume-role-policy-document file://batch-trust-policy.json

# Attach policy
aws iam put-role-policy \
    --role-name BioAgentBatchRole \
    --policy-name BioAgentBatchPolicy \
    --policy-document file://batch-role-policy.json
```

### Step 4: Create Compute Environment

```bash
aws batch create-compute-environment \
    --compute-environment-name bioagent-compute-env \
    --type MANAGED \
    --state ENABLED \
    --compute-resources '{
        "type": "SPOT",
        "allocationStrategy": "SPOT_CAPACITY_OPTIMIZED",
        "minvCpus": 0,
        "maxvCpus": 256,
        "desiredvCpus": 0,
        "instanceTypes": ["optimal"],
        "subnets": ["subnet-xxxxx"],
        "securityGroupIds": ["sg-xxxxx"],
        "instanceRole": "arn:aws:iam::ACCOUNT:instance-profile/ecsInstanceRole"
    }'
```

### Step 5: Create Job Queue

```bash
aws batch create-job-queue \
    --job-queue-name bioagent-queue \
    --state ENABLED \
    --priority 1 \
    --compute-environment-order '[
        {"order": 1, "computeEnvironment": "bioagent-compute-env"}
    ]'
```

### Step 6: Create Job Definition

```bash
aws batch register-job-definition \
    --job-definition-name bioagent-job-def \
    --type container \
    --container-properties '{
        "image": "bioagent/executor:latest",
        "resourceRequirements": [
            {"type": "VCPU", "value": "4"},
            {"type": "MEMORY", "value": "16384"}
        ],
        "jobRoleArn": "arn:aws:iam::ACCOUNT:role/BioAgentBatchRole"
    }'
```

### Step 7: Set Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export AWS_REGION="us-east-1"
export AWS_S3_BUCKET="my-bioagent-data"
export AWS_BATCH_QUEUE="bioagent-queue"
export AWS_BATCH_JOB_DEF="bioagent-job-def"

# Optional: For ECR container registry
export AWS_ECR_REGISTRY="123456789.dkr.ecr.us-east-1.amazonaws.com"
```

---

## Google Cloud Life Sciences Setup

GCP Life Sciences API is optimized for genomics workloads with built-in support for common tools.

### Step 1: Install Google Cloud SDK

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
gcloud init
gcloud auth application-default login

# Install Python SDK
pip install google-cloud-life-sciences google-cloud-storage
```

### Step 2: Enable Required APIs

```bash
gcloud services enable lifesciences.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable compute.googleapis.com
```

### Step 3: Create GCS Bucket

```bash
# Create bucket
gsutil mb -l us-central1 gs://my-bioagent-bucket

# Set lifecycle policy (auto-delete old files)
cat > lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://my-bioagent-bucket
```

### Step 4: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create bioagent-executor \
    --display-name="BioAgent Executor"

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:bioagent-executor@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/lifesciences.workflowsRunner"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:bioagent-executor@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Download key (store securely!)
gcloud iam service-accounts keys create ~/bioagent-gcp-key.json \
    --iam-account=bioagent-executor@PROJECT_ID.iam.gserviceaccount.com
```

### Step 5: Set Environment Variables

```bash
export GCP_PROJECT="my-project-id"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GCP_GCS_BUCKET="my-bioagent-bucket"
export GCP_SERVICE_ACCOUNT="bioagent-executor@my-project-id.iam.gserviceaccount.com"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/bioagent-gcp-key.json"
```

---

## Azure Batch Setup

Azure Batch provides enterprise-grade batch computing with integration to Azure ecosystem.

### Step 1: Install Azure CLI and SDK

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login

# Install Python SDK
pip install azure-batch azure-storage-blob
```

### Step 2: Create Resource Group

```bash
az group create \
    --name bioagent-rg \
    --location eastus
```

### Step 3: Create Storage Account

```bash
# Create storage account
az storage account create \
    --name bioagentstorageacct \
    --resource-group bioagent-rg \
    --location eastus \
    --sku Standard_LRS

# Get connection string
az storage account show-connection-string \
    --name bioagentstorageacct \
    --resource-group bioagent-rg

# Create container
az storage container create \
    --name bioagent-data \
    --account-name bioagentstorageacct
```

### Step 4: Create Batch Account

```bash
# Create batch account
az batch account create \
    --name bioagentbatch \
    --resource-group bioagent-rg \
    --location eastus \
    --storage-account bioagentstorageacct

# Get account key
az batch account keys list \
    --name bioagentbatch \
    --resource-group bioagent-rg
```

### Step 5: Set Environment Variables

```bash
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="bioagent-rg"
export AZURE_BATCH_ACCOUNT="bioagentbatch"
export AZURE_BATCH_KEY="your-batch-key"
export AZURE_STORAGE_ACCOUNT="bioagentstorageacct"
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
export AZURE_CONTAINER="bioagent-data"
```

---

## SLURM HPC Setup

SLURM is the most common workload manager for on-premise HPC clusters.

### Step 1: Install SSH Client

```bash
pip install paramiko
```

### Step 2: Configure SSH Access

```bash
# Generate SSH key if needed
ssh-keygen -t rsa -b 4096 -f ~/.ssh/bioagent_cluster

# Copy to cluster
ssh-copy-id -i ~/.ssh/bioagent_cluster.pub user@cluster.example.edu

# Test connection
ssh -i ~/.ssh/bioagent_cluster user@cluster.example.edu "sinfo"
```

### Step 3: Identify Cluster Configuration

Connect to your cluster and gather information:

```bash
# List partitions
sinfo -s

# Example output:
# PARTITION   AVAIL  TIMELIMIT  NODES  STATE
# default*      up   infinite     50  idle
# gpu           up   7-00:00:00   10  idle
# highmem       up   3-00:00:00    5  idle

# Check your account
sacctmgr show user $USER

# Find work directory
echo $SCRATCH  # or $WORK
```

### Step 4: Set Environment Variables

```bash
export SLURM_HOST="cluster.example.edu"
export SLURM_USER="your_username"
export SLURM_PARTITION="default"        # or "gpu" for GPU jobs
export SLURM_ACCOUNT="your_allocation"  # if required
export SLURM_SSH_KEY="$HOME/.ssh/bioagent_cluster"
export SLURM_WORK_DIR="/scratch/$USER/bioagent"
```

### Step 5: Prepare Work Directory

```bash
# On the cluster
ssh -i ~/.ssh/bioagent_cluster user@cluster.example.edu
mkdir -p /scratch/$USER/bioagent
```

---

## Environment Variables Reference

### Complete Reference Table

| Variable | Backend | Required | Default | Description |
|----------|---------|----------|---------|-------------|
| `AWS_REGION` | AWS | No | us-east-1 | AWS region |
| `AWS_S3_BUCKET` | AWS | Yes | - | S3 bucket for data |
| `AWS_BATCH_QUEUE` | AWS | Yes | - | Batch job queue name |
| `AWS_BATCH_JOB_DEF` | AWS | No | bioagent-job-def | Job definition name |
| `AWS_ECR_REGISTRY` | AWS | No | - | ECR registry URL |
| `GCP_PROJECT` | GCP | Yes | - | GCP project ID |
| `GCP_REGION` | GCP | No | us-central1 | GCP region |
| `GCP_ZONE` | GCP | No | us-central1-a | GCP zone |
| `GCP_GCS_BUCKET` | GCP | Yes | - | GCS bucket name |
| `GCP_SERVICE_ACCOUNT` | GCP | No | - | Service account email |
| `AZURE_SUBSCRIPTION_ID` | Azure | Yes | - | Azure subscription |
| `AZURE_RESOURCE_GROUP` | Azure | Yes | - | Resource group name |
| `AZURE_BATCH_ACCOUNT` | Azure | Yes | - | Batch account name |
| `AZURE_BATCH_KEY` | Azure | Yes | - | Batch account key |
| `AZURE_STORAGE_ACCOUNT` | Azure | Yes | - | Storage account name |
| `AZURE_CONTAINER` | Azure | No | bioagent | Blob container name |
| `SLURM_HOST` | SLURM | Yes | - | Cluster hostname |
| `SLURM_USER` | SLURM | Yes | - | SSH username |
| `SLURM_PARTITION` | SLURM | No | default | SLURM partition |
| `SLURM_ACCOUNT` | SLURM | No | - | SLURM account |
| `SLURM_SSH_KEY` | SLURM | No | ~/.ssh/id_rsa | SSH key path |
| `SLURM_WORK_DIR` | SLURM | No | /scratch | Working directory |

### Global Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_PREFER_SPOT` | true | Use spot/preemptible by default |
| `CLOUD_MAX_HOURLY_COST` | 10.0 | Maximum hourly spend limit |

### Example .env File

```bash
# ~/.bioagent.env

# AWS Batch
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-bioagent-bucket
AWS_BATCH_QUEUE=bioagent-queue
AWS_BATCH_JOB_DEF=bioagent-job-def

# GCP Life Sciences
GCP_PROJECT=my-gcp-project
GCP_GCS_BUCKET=my-bioagent-bucket
GOOGLE_APPLICATION_CREDENTIALS=/home/user/gcp-key.json

# SLURM
SLURM_HOST=cluster.university.edu
SLURM_USER=researcher
SLURM_PARTITION=gpu
SLURM_WORK_DIR=/scratch/researcher/bioagent

# Global
CLOUD_PREFER_SPOT=true
CLOUD_MAX_HOURLY_COST=20.0
```

Load with: `source ~/.bioagent.env`

---

## Testing Your Setup

### Verify Configuration

```python
from cloud import CloudConfig, CloudExecutor

# Load config
config = CloudConfig.from_env()

# Check which backends are available
print("AWS configured:", config.is_aws_configured())
print("GCP configured:", config.is_gcp_configured())
print("Azure configured:", config.is_azure_configured())
print("SLURM configured:", config.is_slurm_configured())

# Create executor
executor = CloudExecutor(config)
print("Available backends:", [b.value for b in executor.get_available_backends()])
```

### Test Job Submission

```python
from cloud import CloudExecutor, ResourceSpec

executor = CloudExecutor()

# Define resources
resources = ResourceSpec(
    vcpus=2,
    memory_gb=4,
    timeout_hours=1,
    use_spot=True,
)

# Submit test job
job_id = executor.submit_job(
    command="echo 'Hello from cloud!' && sleep 10 && echo 'Done!'",
    resources=resources,
    name="bioagent-test-job",
)

print(f"Submitted job: {job_id}")

# Check status
import time
for _ in range(10):
    status = executor.get_job_status(job_id)
    print(f"Status: {status.status.value}")
    if status.status.value in ("succeeded", "failed"):
        break
    time.sleep(30)

# Get logs
logs = executor.get_job_logs(job_id)
print(logs)
```

### Test from BioAgent CLI

```bash
# Start BioAgent
python -m bioagent

# In the chat:
> Estimate the cost of running a job with 8 CPUs, 32GB RAM for 4 hours

> Submit a test job that runs "echo hello world" on AWS Batch with 2 CPUs
```

---

## Troubleshooting

### AWS Batch Issues

**Job stuck in RUNNABLE state**
```bash
# Check compute environment
aws batch describe-compute-environments --compute-environments bioagent-compute-env

# Verify subnets have internet access (for pulling containers)
# Verify security groups allow outbound traffic
```

**Permission denied errors**
```bash
# Verify IAM role has correct permissions
aws iam get-role-policy --role-name BioAgentBatchRole --policy-name BioAgentBatchPolicy
```

### GCP Life Sciences Issues

**API not enabled**
```bash
gcloud services enable lifesciences.googleapis.com
```

**Quota exceeded**
```bash
# Check quotas
gcloud compute project-info describe --project PROJECT_ID
# Request increase at: https://console.cloud.google.com/iam-admin/quotas
```

### Azure Batch Issues

**Pool creation fails**
```bash
# Check available VM sizes in region
az vm list-sizes --location eastus --output table
```

**Authentication errors**
```bash
# Regenerate keys
az batch account keys renew --name bioagentbatch --resource-group bioagent-rg
```

### SLURM Issues

**SSH connection fails**
```bash
# Test SSH manually
ssh -v -i ~/.ssh/bioagent_cluster user@cluster.example.edu

# Check if key is added to agent
ssh-add -l
ssh-add ~/.ssh/bioagent_cluster
```

**Job fails immediately**
```bash
# Check SLURM logs on cluster
ssh user@cluster "cat /scratch/user/bioagent/*.err"

# Verify partition exists
ssh user@cluster "sinfo -p gpu"
```

### General Debugging

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test individual components
from cloud.aws import AWSBatchExecutor
from cloud import CloudConfig

config = CloudConfig.from_env()
executor = AWSBatchExecutor(config)

# This will show detailed errors
try:
    job_id = executor.submit_job("echo test")
except Exception as e:
    print(f"Error: {e}")
```

---

## Cost Management Tips

1. **Always use spot/preemptible instances** for fault-tolerant workloads (default in BioAgent)

2. **Set appropriate timeouts** to avoid runaway costs:
   ```python
   ResourceSpec(timeout_hours=4)  # Job killed after 4 hours
   ```

3. **Use auto-scaling** with min=0 to avoid idle costs

4. **Monitor spending**:
   - AWS: Set up Budgets and Cost Alerts
   - GCP: Set up Budget Alerts
   - Azure: Set up Cost Alerts

5. **Clean up old data**:
   ```bash
   # AWS - delete old files
   aws s3 rm s3://bucket/outputs/ --recursive --exclude "*" --include "*.tmp"

   # GCP - lifecycle policies handle this automatically
   ```

---

## Next Steps

- [BioAgent Multi-Agent System](./multi-agent.md) - Learn how specialists use cloud tools
- [Workflow Integration](./workflows.md) - Run Nextflow/Snakemake on cloud
- [GPU Workloads](./gpu-setup.md) - Configure GPU instances for ML
