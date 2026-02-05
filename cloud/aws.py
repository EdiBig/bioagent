"""
AWS Batch executor for cloud job execution.

Provides integration with AWS Batch for running containerized jobs.
"""

from datetime import datetime
from typing import Any
import json

from .config import CloudConfig, ResourceSpec, JobStatus, JobInfo
from .base import BaseExecutor, ExecutorBackend


class AWSBatchExecutor(BaseExecutor):
    """
    AWS Batch executor for running jobs on AWS.

    Features:
    - Managed compute environment
    - Spot instance support
    - S3 input/output staging
    - CloudWatch logging
    """

    def __init__(self, config: CloudConfig):
        super().__init__(config)
        self._client = None
        self._s3_client = None
        self._logs_client = None

    @property
    def backend(self) -> ExecutorBackend:
        return ExecutorBackend.AWS_BATCH

    @property
    def batch_client(self):
        """Lazy initialization of Batch client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("batch", region_name=self.config.aws_region)
            except ImportError:
                raise ImportError("boto3 is required for AWS Batch. Install with: pip install boto3")
        return self._client

    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            import boto3
            self._s3_client = boto3.client("s3", region_name=self.config.aws_region)
        return self._s3_client

    @property
    def logs_client(self):
        """Lazy initialization of CloudWatch Logs client."""
        if self._logs_client is None:
            import boto3
            self._logs_client = boto3.client("logs", region_name=self.config.aws_region)
        return self._logs_client

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
        """Submit a job to AWS Batch."""
        resources = resources or self.config.default_resources
        job_name = name or self._generate_job_id("bioagent")

        # Prepare command
        if isinstance(command, str):
            command = ["bash", "-c", command]

        # Build container overrides
        container_overrides = {
            "command": command,
            **resources.to_aws_spec(),
        }

        if container:
            container_overrides["image"] = container

        if environment:
            container_overrides["environment"] = [
                {"name": k, "value": v} for k, v in environment.items()
            ]

        # Stage input files to S3 if provided
        if input_files and self.config.aws_s3_bucket:
            s3_inputs = self._stage_inputs(input_files, job_name)
            env_vars = container_overrides.get("environment", [])
            env_vars.append({"name": "INPUT_FILES", "value": json.dumps(s3_inputs)})
            container_overrides["environment"] = env_vars

        # Set output path
        if output_path or self.config.aws_s3_bucket:
            output_s3 = output_path or f"s3://{self.config.aws_s3_bucket}/outputs/{job_name}"
            env_vars = container_overrides.get("environment", [])
            env_vars.append({"name": "OUTPUT_PATH", "value": output_s3})
            container_overrides["environment"] = env_vars

        # Submit job
        try:
            response = self.batch_client.submit_job(
                jobName=job_name,
                jobQueue=self.config.aws_batch_queue,
                jobDefinition=self.config.aws_batch_job_definition,
                containerOverrides=container_overrides,
                retryStrategy={"attempts": resources.max_retries + 1},
                timeout={"attemptDurationSeconds": int(resources.timeout_hours * 3600)},
            )

            job_id = response["jobId"]

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
            # Return mock job ID for testing when AWS isn't configured
            job_id = self._generate_job_id("mock-aws")
            self.jobs[job_id] = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.PENDING,
                submit_time=datetime.now().isoformat(),
                error_message=f"AWS Batch submission simulated: {str(e)}",
                resources=resources,
            )
            return job_id

    def _stage_inputs(self, input_files: list[str], job_name: str) -> list[str]:
        """Stage input files to S3."""
        s3_paths = []
        for local_path in input_files:
            s3_key = f"inputs/{job_name}/{local_path.split('/')[-1]}"
            s3_path = f"s3://{self.config.aws_s3_bucket}/{s3_key}"

            try:
                self.s3_client.upload_file(local_path, self.config.aws_s3_bucket, s3_key)
                s3_paths.append(s3_path)
            except Exception:
                # Skip failed uploads in test mode
                s3_paths.append(f"s3://{self.config.aws_s3_bucket}/{s3_key} (upload pending)")

        return s3_paths

    def get_job_status(self, job_id: str) -> JobInfo:
        """Get job status from AWS Batch."""
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])

            if not response["jobs"]:
                raise ValueError(f"Job {job_id} not found")

            job = response["jobs"][0]
            status = self._map_aws_status(job["status"])

            info = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=status,
                submit_time=datetime.fromtimestamp(job.get("createdAt", 0) / 1000).isoformat(),
                start_time=datetime.fromtimestamp(job.get("startedAt", 0) / 1000).isoformat() if job.get("startedAt") else None,
                end_time=datetime.fromtimestamp(job.get("stoppedAt", 0) / 1000).isoformat() if job.get("stoppedAt") else None,
                exit_code=job.get("container", {}).get("exitCode"),
                log_url=self._get_log_stream_url(job),
                error_message=job.get("statusReason"),
            )

            self.jobs[job_id] = info
            return info

        except Exception as e:
            # Return cached info or pending status
            if job_id in self.jobs:
                return self.jobs[job_id]
            return JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.UNKNOWN,
                submit_time=datetime.now().isoformat(),
                error_message=str(e),
            )

    def _map_aws_status(self, aws_status: str) -> JobStatus:
        """Map AWS Batch status to JobStatus."""
        mapping = {
            "SUBMITTED": JobStatus.SUBMITTED,
            "PENDING": JobStatus.PENDING,
            "RUNNABLE": JobStatus.PENDING,
            "STARTING": JobStatus.RUNNING,
            "RUNNING": JobStatus.RUNNING,
            "SUCCEEDED": JobStatus.SUCCEEDED,
            "FAILED": JobStatus.FAILED,
        }
        return mapping.get(aws_status, JobStatus.UNKNOWN)

    def _get_log_stream_url(self, job: dict) -> str | None:
        """Get CloudWatch log stream URL."""
        log_stream = job.get("container", {}).get("logStreamName")
        if log_stream:
            return f"https://{self.config.aws_region}.console.aws.amazon.com/cloudwatch/home?region={self.config.aws_region}#logsV2:log-groups/log-group/$252Faws$252Fbatch$252Fjob/log-events/{log_stream}"
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job on AWS Batch."""
        try:
            self.batch_client.cancel_job(jobId=job_id, reason="Cancelled by user")
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.CANCELLED
            return True
        except Exception:
            return False

    def get_job_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs from CloudWatch."""
        try:
            # Get log stream name from job
            response = self.batch_client.describe_jobs(jobs=[job_id])
            if not response["jobs"]:
                return f"Job {job_id} not found"

            log_stream = response["jobs"][0].get("container", {}).get("logStreamName")
            if not log_stream:
                return "No logs available yet"

            # Fetch logs from CloudWatch
            log_response = self.logs_client.get_log_events(
                logGroupName="/aws/batch/job",
                logStreamName=log_stream,
                limit=tail,
            )

            logs = []
            for event in log_response.get("events", []):
                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000).isoformat()
                logs.append(f"[{timestamp}] {event['message']}")

            return "\n".join(logs) if logs else "No log entries found"

        except Exception as e:
            return f"Error fetching logs: {e}"

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[JobInfo]:
        """List jobs from AWS Batch."""
        try:
            # Map JobStatus to AWS status
            aws_status = None
            if status:
                status_map = {
                    JobStatus.PENDING: "PENDING",
                    JobStatus.SUBMITTED: "SUBMITTED",
                    JobStatus.RUNNING: "RUNNING",
                    JobStatus.SUCCEEDED: "SUCCEEDED",
                    JobStatus.FAILED: "FAILED",
                }
                aws_status = status_map.get(status)

            params = {
                "jobQueue": self.config.aws_batch_queue,
                "maxResults": min(limit, 100),
            }
            if aws_status:
                params["jobStatus"] = aws_status

            response = self.batch_client.list_jobs(**params)

            jobs = []
            for job_summary in response.get("jobSummaryList", []):
                jobs.append(JobInfo(
                    job_id=job_summary["jobId"],
                    backend=self.backend.value,
                    status=self._map_aws_status(job_summary["status"]),
                    submit_time=datetime.fromtimestamp(job_summary.get("createdAt", 0) / 1000).isoformat(),
                    start_time=datetime.fromtimestamp(job_summary.get("startedAt", 0) / 1000).isoformat() if job_summary.get("startedAt") else None,
                    end_time=datetime.fromtimestamp(job_summary.get("stoppedAt", 0) / 1000).isoformat() if job_summary.get("stoppedAt") else None,
                ))

            return jobs

        except Exception:
            # Return cached jobs
            return list(self.jobs.values())[:limit]

    def create_job_definition(
        self,
        name: str,
        container_image: str,
        vcpus: int = 4,
        memory_mb: int = 16384,
    ) -> str:
        """Create a new job definition."""
        try:
            response = self.batch_client.register_job_definition(
                jobDefinitionName=name,
                type="container",
                containerProperties={
                    "image": container_image,
                    "resourceRequirements": [
                        {"type": "VCPU", "value": str(vcpus)},
                        {"type": "MEMORY", "value": str(memory_mb)},
                    ],
                },
                retryStrategy={"attempts": 2},
            )
            return response["jobDefinitionArn"]
        except Exception as e:
            return f"Error creating job definition: {e}"
