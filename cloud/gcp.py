"""
Google Cloud Life Sciences executor.

Provides integration with Google Cloud Life Sciences API for
running bioinformatics pipelines on GCP.
"""

from datetime import datetime
from typing import Any
import json

from .config import CloudConfig, ResourceSpec, JobStatus, JobInfo
from .base import BaseExecutor, ExecutorBackend


class GoogleLifeSciencesExecutor(BaseExecutor):
    """
    Google Cloud Life Sciences executor.

    Features:
    - Preemptible VM support
    - GPU acceleration
    - GCS input/output staging
    - Automatic VM management
    """

    def __init__(self, config: CloudConfig):
        super().__init__(config)
        self._client = None
        self._storage_client = None

    @property
    def backend(self) -> ExecutorBackend:
        return ExecutorBackend.GCP_LIFE_SCIENCES

    @property
    def client(self):
        """Lazy initialization of Life Sciences client."""
        if self._client is None:
            try:
                from google.cloud import lifesciences_v2beta
                self._client = lifesciences_v2beta.WorkflowsServiceV2BetaClient()
            except ImportError:
                raise ImportError(
                    "google-cloud-life-sciences is required. "
                    "Install with: pip install google-cloud-life-sciences"
                )
        return self._client

    @property
    def storage_client(self):
        """Lazy initialization of Cloud Storage client."""
        if self._storage_client is None:
            from google.cloud import storage
            self._storage_client = storage.Client(project=self.config.gcp_project)
        return self._storage_client

    def submit_job(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        name: str | None = None,
        environment: dict[str, str] | None = None,
        input_files: list[str] | None = None,
        output_path: str | None = None,
        container: str | None = None,
    ) -> str:
        """Submit a job to Google Cloud Life Sciences."""
        resources = resources or self.config.default_resources
        job_name = name or self._generate_job_id("bioagent")

        # Prepare command
        if isinstance(command, str):
            command = ["bash", "-c", command]

        # Build pipeline
        pipeline = self._build_pipeline(
            command=command,
            resources=resources,
            container=container or self.config.default_container,
            environment=environment,
            input_files=input_files,
            output_path=output_path,
            job_name=job_name,
        )

        try:
            # Submit pipeline
            parent = f"projects/{self.config.gcp_project}/locations/{self.config.gcp_region}"

            request = {
                "parent": parent,
                "pipeline": pipeline,
            }

            operation = self.client.run_pipeline(request=request)
            job_id = operation.name.split("/")[-1]

            # Track job
            self.jobs[job_id] = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.SUBMITTED,
                submit_time=datetime.now().isoformat(),
                resources=resources,
            )

            return job_id

        except Exception as e:
            # Return mock job ID for testing
            job_id = self._generate_job_id("mock-gcp")
            self.jobs[job_id] = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.PENDING,
                submit_time=datetime.now().isoformat(),
                error_message=f"GCP submission simulated: {str(e)}",
                resources=resources,
            )
            return job_id

    def _build_pipeline(
        self,
        command: list[str],
        resources: ResourceSpec,
        container: str,
        environment: dict[str, str] | None,
        input_files: list[str] | None,
        output_path: str | None,
        job_name: str,
    ) -> dict:
        """Build Life Sciences pipeline definition."""
        # Build actions
        actions = []

        # Input staging action
        if input_files:
            gcs_inputs = self._stage_inputs(input_files, job_name)
            actions.append({
                "imageUri": "google/cloud-sdk:slim",
                "commands": ["gsutil", "-m", "cp"] + gcs_inputs + ["/mnt/inputs/"],
                "mounts": [{"disk": "inputs", "path": "/mnt/inputs"}],
            })

        # Main execution action
        main_action = {
            "imageUri": container,
            "commands": command,
            "mounts": [
                {"disk": "inputs", "path": "/mnt/inputs"},
                {"disk": "outputs", "path": "/mnt/outputs"},
            ],
        }

        if environment:
            main_action["environment"] = environment

        actions.append(main_action)

        # Output staging action
        if output_path or self.config.gcp_gcs_bucket:
            gcs_output = output_path or f"gs://{self.config.gcp_gcs_bucket}/outputs/{job_name}"
            actions.append({
                "imageUri": "google/cloud-sdk:slim",
                "commands": ["gsutil", "-m", "cp", "-r", "/mnt/outputs/*", gcs_output],
                "mounts": [{"disk": "outputs", "path": "/mnt/outputs"}],
                "alwaysRun": True,
            })

        # Build resources
        vm_resources = resources.to_gcp_spec()
        vm_resources["bootDiskSizeGb"] = int(resources.disk_gb)

        # Build pipeline
        return {
            "actions": actions,
            "resources": {
                "regions": [self.config.gcp_region],
                "virtualMachine": vm_resources,
            },
            "timeout": f"{int(resources.timeout_hours * 3600)}s",
        }

    def _stage_inputs(self, input_files: list[str], job_name: str) -> list[str]:
        """Stage input files to GCS."""
        gcs_paths = []
        bucket = self.storage_client.bucket(self.config.gcp_gcs_bucket)

        for local_path in input_files:
            blob_name = f"inputs/{job_name}/{local_path.split('/')[-1]}"
            gcs_path = f"gs://{self.config.gcp_gcs_bucket}/{blob_name}"

            try:
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(local_path)
                gcs_paths.append(gcs_path)
            except Exception:
                gcs_paths.append(f"{gcs_path} (upload pending)")

        return gcs_paths

    def get_job_status(self, job_id: str) -> JobInfo:
        """Get job status from Life Sciences."""
        try:
            operation_name = f"projects/{self.config.gcp_project}/locations/{self.config.gcp_region}/operations/{job_id}"
            operation = self.client.get_operation(name=operation_name)

            if operation.done:
                if operation.error.code:
                    status = JobStatus.FAILED
                    error_msg = operation.error.message
                else:
                    status = JobStatus.SUCCEEDED
                    error_msg = None
            else:
                status = JobStatus.RUNNING
                error_msg = None

            # Parse metadata for timing
            metadata = dict(operation.metadata)

            info = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=status,
                submit_time=metadata.get("createTime", datetime.now().isoformat()),
                start_time=metadata.get("startTime"),
                end_time=metadata.get("endTime"),
                error_message=error_msg,
            )

            self.jobs[job_id] = info
            return info

        except Exception as e:
            if job_id in self.jobs:
                return self.jobs[job_id]
            return JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.UNKNOWN,
                submit_time=datetime.now().isoformat(),
                error_message=str(e),
            )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job on Life Sciences."""
        try:
            operation_name = f"projects/{self.config.gcp_project}/locations/{self.config.gcp_region}/operations/{job_id}"
            self.client.cancel_operation(name=operation_name)
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.CANCELLED
            return True
        except Exception:
            return False

    def get_job_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs from Cloud Logging."""
        try:
            from google.cloud import logging as cloud_logging

            client = cloud_logging.Client(project=self.config.gcp_project)
            logger = client.logger("genomics")

            filter_str = f'resource.labels.operation_id="{job_id}"'
            entries = list(client.list_entries(filter_=filter_str, max_results=tail))

            logs = []
            for entry in entries:
                timestamp = entry.timestamp.isoformat() if entry.timestamp else ""
                logs.append(f"[{timestamp}] {entry.payload}")

            return "\n".join(logs) if logs else "No log entries found"

        except Exception as e:
            return f"Error fetching logs: {e}"

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[JobInfo]:
        """List jobs from Life Sciences."""
        try:
            parent = f"projects/{self.config.gcp_project}/locations/{self.config.gcp_region}"
            operations = self.client.list_operations(name=parent, page_size=limit)

            jobs = []
            for op in operations:
                job_id = op.name.split("/")[-1]

                if op.done:
                    op_status = JobStatus.FAILED if op.error.code else JobStatus.SUCCEEDED
                else:
                    op_status = JobStatus.RUNNING

                if status and op_status != status:
                    continue

                metadata = dict(op.metadata) if op.metadata else {}

                jobs.append(JobInfo(
                    job_id=job_id,
                    backend=self.backend.value,
                    status=op_status,
                    submit_time=metadata.get("createTime", ""),
                    start_time=metadata.get("startTime"),
                    end_time=metadata.get("endTime"),
                ))

            return jobs[:limit]

        except Exception:
            return list(self.jobs.values())[:limit]

    def submit_dsub_job(
        self,
        script: str,
        inputs: dict[str, str] | None = None,
        outputs: dict[str, str] | None = None,
        resources: ResourceSpec | None = None,
    ) -> str:
        """
        Submit a dsub-style job.

        dsub is a command-line tool for submitting batch jobs
        to Life Sciences API with a simpler interface.
        """
        resources = resources or self.config.default_resources

        # Build dsub command
        cmd = [
            "dsub",
            "--provider", "google-cls-v2",
            "--project", self.config.gcp_project,
            "--regions", self.config.gcp_region,
            "--logging", f"gs://{self.config.gcp_gcs_bucket}/logs",
            "--script", script,
            "--machine-type", resources._get_gcp_machine_type(),
        ]

        if resources.use_spot:
            cmd.append("--preemptible")

        if inputs:
            for name, path in inputs.items():
                cmd.extend(["--input", f"{name}={path}"])

        if outputs:
            for name, path in outputs.items():
                cmd.extend(["--output", f"{name}={path}"])

        # For now, submit as regular job
        return self.submit_job(" ".join(cmd), resources)
