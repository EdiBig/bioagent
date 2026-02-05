"""
Cloud configuration and resource specifications.

Defines common configuration for all cloud/HPC backends.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import os
import json


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class InstanceType(Enum):
    """Common instance type categories."""
    STANDARD = "standard"       # General purpose
    COMPUTE = "compute"         # CPU-optimized
    MEMORY = "memory"           # Memory-optimized
    GPU = "gpu"                 # GPU instances
    SPOT = "spot"               # Spot/preemptible


@dataclass
class ResourceSpec:
    """
    Resource specification for cloud jobs.

    Defines CPU, memory, GPU, and storage requirements.
    """

    # CPU and memory
    vcpus: int = 4
    memory_gb: float = 16.0

    # GPU (optional)
    gpu_count: int = 0
    gpu_type: str | None = None  # e.g., "nvidia-tesla-v100", "nvidia-tesla-t4"

    # Storage
    disk_gb: float = 100.0

    # Timeout
    timeout_hours: float = 24.0

    # Instance preferences
    instance_type: InstanceType = InstanceType.STANDARD
    use_spot: bool = False
    spot_max_price: float | None = None  # Max hourly price for spot

    # Retry policy
    max_retries: int = 2
    retry_on_spot_interruption: bool = True

    def to_aws_spec(self) -> dict:
        """Convert to AWS Batch resource requirements."""
        resources = [
            {"type": "VCPU", "value": str(self.vcpus)},
            {"type": "MEMORY", "value": str(int(self.memory_gb * 1024))},
        ]
        if self.gpu_count > 0:
            resources.append({"type": "GPU", "value": str(self.gpu_count)})
        return {
            "resourceRequirements": resources,
            "timeout": {"attemptDurationSeconds": int(self.timeout_hours * 3600)},
        }

    def to_gcp_spec(self) -> dict:
        """Convert to GCP Life Sciences resource specification."""
        machine_type = self._get_gcp_machine_type()
        spec = {
            "machineType": machine_type,
            "preemptible": self.use_spot,
        }
        if self.gpu_count > 0:
            spec["accelerators"] = [{
                "type": self.gpu_type or "nvidia-tesla-t4",
                "count": self.gpu_count,
            }]
        return spec

    def _get_gcp_machine_type(self) -> str:
        """Determine GCP machine type from resources."""
        if self.instance_type == InstanceType.MEMORY:
            return f"n1-highmem-{self.vcpus}"
        elif self.instance_type == InstanceType.COMPUTE:
            return f"c2-standard-{self.vcpus}"
        else:
            return f"n1-standard-{self.vcpus}"

    def to_azure_spec(self) -> dict:
        """Convert to Azure Batch pool specification."""
        vm_size = self._get_azure_vm_size()
        return {
            "vmSize": vm_size,
            "targetDedicatedNodes": 0 if self.use_spot else 1,
            "targetLowPriorityNodes": 1 if self.use_spot else 0,
        }

    def _get_azure_vm_size(self) -> str:
        """Determine Azure VM size from resources."""
        if self.gpu_count > 0:
            return "Standard_NC6"
        elif self.instance_type == InstanceType.MEMORY:
            return f"Standard_E{self.vcpus}_v3"
        elif self.instance_type == InstanceType.COMPUTE:
            return f"Standard_F{self.vcpus}s_v2"
        else:
            return f"Standard_D{self.vcpus}_v3"

    def to_slurm_spec(self) -> dict:
        """Convert to SLURM sbatch directives."""
        spec = {
            "cpus-per-task": self.vcpus,
            "mem": f"{int(self.memory_gb)}G",
            "time": self._hours_to_slurm_time(self.timeout_hours),
        }
        if self.gpu_count > 0:
            gpu_spec = f"{self.gpu_type}:{self.gpu_count}" if self.gpu_type else str(self.gpu_count)
            spec["gres"] = f"gpu:{gpu_spec}"
        return spec

    def _hours_to_slurm_time(self, hours: float) -> str:
        """Convert hours to SLURM time format (D-HH:MM:SS)."""
        total_seconds = int(hours * 3600)
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if days > 0:
            return f"{days}-{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class CloudConfig:
    """
    Cloud execution configuration.

    Stores credentials, regions, and default settings for cloud backends.
    """

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_batch_queue: str = "bioagent-queue"
    aws_batch_job_definition: str = "bioagent-job-def"
    aws_s3_bucket: str = ""
    aws_ecr_registry: str = ""

    # GCP Configuration
    gcp_project: str = ""
    gcp_region: str = "us-central1"
    gcp_zone: str = "us-central1-a"
    gcp_gcs_bucket: str = ""
    gcp_service_account: str = ""

    # Azure Configuration
    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    azure_batch_account: str = ""
    azure_storage_account: str = ""
    azure_container: str = ""

    # SLURM Configuration
    slurm_host: str = ""
    slurm_user: str = ""
    slurm_partition: str = "default"
    slurm_account: str = ""
    slurm_ssh_key: str = ""
    slurm_work_dir: str = "/scratch"

    # Default resources
    default_resources: ResourceSpec = field(default_factory=ResourceSpec)

    # Container settings
    default_container: str = "bioagent/executor:latest"
    use_gpu_container: str = "bioagent/executor-gpu:latest"

    # Cost management
    max_hourly_cost: float = 10.0  # Maximum hourly spend
    prefer_spot: bool = True

    @classmethod
    def from_env(cls) -> "CloudConfig":
        """Create configuration from environment variables."""
        return cls(
            # AWS
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_batch_queue=os.getenv("AWS_BATCH_QUEUE", "bioagent-queue"),
            aws_batch_job_definition=os.getenv("AWS_BATCH_JOB_DEF", "bioagent-job-def"),
            aws_s3_bucket=os.getenv("AWS_S3_BUCKET", ""),
            aws_ecr_registry=os.getenv("AWS_ECR_REGISTRY", ""),
            # GCP
            gcp_project=os.getenv("GCP_PROJECT", ""),
            gcp_region=os.getenv("GCP_REGION", "us-central1"),
            gcp_zone=os.getenv("GCP_ZONE", "us-central1-a"),
            gcp_gcs_bucket=os.getenv("GCP_GCS_BUCKET", ""),
            gcp_service_account=os.getenv("GCP_SERVICE_ACCOUNT", ""),
            # Azure
            azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
            azure_batch_account=os.getenv("AZURE_BATCH_ACCOUNT", ""),
            azure_storage_account=os.getenv("AZURE_STORAGE_ACCOUNT", ""),
            azure_container=os.getenv("AZURE_CONTAINER", ""),
            # SLURM
            slurm_host=os.getenv("SLURM_HOST", ""),
            slurm_user=os.getenv("SLURM_USER", ""),
            slurm_partition=os.getenv("SLURM_PARTITION", "default"),
            slurm_account=os.getenv("SLURM_ACCOUNT", ""),
            slurm_ssh_key=os.getenv("SLURM_SSH_KEY", ""),
            slurm_work_dir=os.getenv("SLURM_WORK_DIR", "/scratch"),
            # Defaults
            prefer_spot=os.getenv("CLOUD_PREFER_SPOT", "true").lower() == "true",
            max_hourly_cost=float(os.getenv("CLOUD_MAX_HOURLY_COST", "10.0")),
        )

    @classmethod
    def from_file(cls, path: str) -> "CloudConfig":
        """Load configuration from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def save(self, path: str):
        """Save configuration to JSON file."""
        data = {
            "aws_region": self.aws_region,
            "aws_batch_queue": self.aws_batch_queue,
            "aws_batch_job_definition": self.aws_batch_job_definition,
            "aws_s3_bucket": self.aws_s3_bucket,
            "gcp_project": self.gcp_project,
            "gcp_region": self.gcp_region,
            "gcp_gcs_bucket": self.gcp_gcs_bucket,
            "azure_subscription_id": self.azure_subscription_id,
            "azure_resource_group": self.azure_resource_group,
            "slurm_host": self.slurm_host,
            "slurm_partition": self.slurm_partition,
            "prefer_spot": self.prefer_spot,
            "max_hourly_cost": self.max_hourly_cost,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def is_aws_configured(self) -> bool:
        """Check if AWS is configured."""
        return bool(self.aws_s3_bucket)

    def is_gcp_configured(self) -> bool:
        """Check if GCP is configured."""
        return bool(self.gcp_project and self.gcp_gcs_bucket)

    def is_azure_configured(self) -> bool:
        """Check if Azure is configured."""
        return bool(self.azure_subscription_id and self.azure_batch_account)

    def is_slurm_configured(self) -> bool:
        """Check if SLURM is configured."""
        return bool(self.slurm_host)


@dataclass
class JobInfo:
    """Information about a submitted job."""

    job_id: str
    backend: str
    status: JobStatus
    submit_time: str
    start_time: str | None = None
    end_time: str | None = None
    exit_code: int | None = None
    log_url: str | None = None
    output_path: str | None = None
    error_message: str | None = None
    cost_estimate: float | None = None
    resources: ResourceSpec | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "backend": self.backend,
            "status": self.status.value,
            "submit_time": self.submit_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "exit_code": self.exit_code,
            "log_url": self.log_url,
            "output_path": self.output_path,
            "error_message": self.error_message,
            "cost_estimate": self.cost_estimate,
        }
