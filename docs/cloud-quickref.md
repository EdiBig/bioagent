# Cloud Backend Quick Reference

## Minimum Setup (Pick One)

### AWS Batch
```bash
export AWS_S3_BUCKET="your-bucket"
export AWS_BATCH_QUEUE="your-queue"
```

### Google Cloud
```bash
export GCP_PROJECT="your-project"
export GCP_GCS_BUCKET="your-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### Azure Batch
```bash
export AZURE_SUBSCRIPTION_ID="your-sub-id"
export AZURE_BATCH_ACCOUNT="your-account"
export AZURE_STORAGE_ACCOUNT="your-storage"
```

### SLURM HPC
```bash
export SLURM_HOST="cluster.example.edu"
export SLURM_USER="your-username"
```

---

## Common Operations

### Submit a Job
```python
from cloud import CloudExecutor, ResourceSpec

executor = CloudExecutor()
job_id = executor.submit_job(
    command="your-command-here",
    resources=ResourceSpec(vcpus=4, memory_gb=16),
)
```

### Check Status
```python
status = executor.get_job_status(job_id)
print(status.status)  # pending, running, succeeded, failed
```

### Get Logs
```python
logs = executor.get_job_logs(job_id, tail=100)
print(logs)
```

### Cancel Job
```python
executor.cancel_job(job_id)
```

### Estimate Cost
```python
costs = executor.estimate_cost(
    ResourceSpec(vcpus=8, memory_gb=32, gpu_count=1),
    duration_hours=4
)
print(f"Spot: ${costs['spot']}, On-demand: ${costs['on_demand']}")
```

---

## Resource Presets

```python
from cloud import ResourceSpec

# Small (testing)
small = ResourceSpec(vcpus=2, memory_gb=4, timeout_hours=1)

# Standard (most workflows)
standard = ResourceSpec(vcpus=8, memory_gb=32, timeout_hours=24)

# Large (alignment, assembly)
large = ResourceSpec(vcpus=32, memory_gb=128, timeout_hours=48)

# GPU (deep learning)
gpu = ResourceSpec(vcpus=8, memory_gb=64, gpu_count=1, gpu_type="nvidia-tesla-v100")

# Spot instances (70% cheaper, may be interrupted)
spot = ResourceSpec(vcpus=16, memory_gb=64, use_spot=True)
```

---

## BioAgent Tools

| Tool | Usage |
|------|-------|
| `cloud_submit_job` | Submit job with command and resources |
| `cloud_job_status` | Get job state and timing |
| `cloud_job_logs` | Fetch stdout/stderr |
| `cloud_cancel_job` | Stop running job |
| `cloud_list_jobs` | List all jobs |
| `cloud_estimate_cost` | Compare pricing |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No backends available | Set environment variables for at least one backend |
| Job stuck pending | Check compute environment has available capacity |
| Permission denied | Verify IAM/service account permissions |
| SSH connection failed | Test with `ssh -v user@host` |
| Spot instance terminated | Job will auto-retry (default: 2 retries) |
