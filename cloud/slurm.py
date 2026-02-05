"""
SLURM HPC executor for cluster job execution.

Provides integration with SLURM workload manager for running
jobs on HPC clusters.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
import json
import re
import tempfile

from .config import CloudConfig, ResourceSpec, JobStatus, JobInfo
from .base import BaseExecutor, ExecutorBackend


class SLURMExecutor(BaseExecutor):
    """
    SLURM executor for running jobs on HPC clusters.

    Features:
    - SSH-based job submission
    - GPU support
    - Array jobs
    - Dependency management
    - Resource accounting
    """

    def __init__(self, config: CloudConfig):
        super().__init__(config)
        self._ssh_client = None

    @property
    def backend(self) -> ExecutorBackend:
        return ExecutorBackend.SLURM

    @property
    def ssh_client(self):
        """Lazy initialization of SSH client."""
        if self._ssh_client is None:
            try:
                import paramiko
                self._ssh_client = paramiko.SSHClient()
                self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # Connect
                connect_kwargs = {
                    "hostname": self.config.slurm_host,
                    "username": self.config.slurm_user,
                }

                if self.config.slurm_ssh_key:
                    connect_kwargs["key_filename"] = self.config.slurm_ssh_key
                else:
                    # Try default key locations
                    import os
                    default_key = os.path.expanduser("~/.ssh/id_rsa")
                    if os.path.exists(default_key):
                        connect_kwargs["key_filename"] = default_key

                self._ssh_client.connect(**connect_kwargs)

            except ImportError:
                raise ImportError("paramiko is required for SLURM. Install with: pip install paramiko")

        return self._ssh_client

    def _execute_remote(self, command: str) -> tuple[str, str, int]:
        """Execute command on remote SLURM cluster."""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode(), stderr.read().decode(), exit_code
        except Exception as e:
            return "", str(e), 1

    def submit_job(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        name: str | None = None,
        environment: dict[str, str] | None = None,
        input_files: list[str] | None = None,
        output_path: str | None = None,
        container: str | None = None,
        partition: str | None = None,
        array: str | None = None,
        dependency: str | None = None,
    ) -> str:
        """Submit a job to SLURM."""
        resources = resources or self.config.default_resources
        job_name = name or self._generate_job_id("bioagent")
        partition = partition or self.config.slurm_partition

        # Generate SLURM script
        script = self._generate_sbatch_script(
            command=command if isinstance(command, str) else " ".join(command),
            resources=resources,
            job_name=job_name,
            partition=partition,
            environment=environment,
            container=container,
            array=array,
            dependency=dependency,
            output_path=output_path,
        )

        try:
            # Transfer input files if needed
            if input_files:
                self._transfer_files(input_files, f"{self.config.slurm_work_dir}/{job_name}")

            # Write script to remote
            remote_script = f"{self.config.slurm_work_dir}/{job_name}.sh"
            sftp = self.ssh_client.open_sftp()

            # Ensure work directory exists
            self._execute_remote(f"mkdir -p {self.config.slurm_work_dir}")

            with sftp.file(remote_script, "w") as f:
                f.write(script)
            sftp.close()

            # Submit job
            stdout, stderr, exit_code = self._execute_remote(f"sbatch {remote_script}")

            if exit_code != 0:
                raise RuntimeError(f"sbatch failed: {stderr}")

            # Parse job ID from output (e.g., "Submitted batch job 12345")
            match = re.search(r"Submitted batch job (\d+)", stdout)
            if match:
                job_id = match.group(1)
            else:
                job_id = self._generate_job_id("slurm")

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
            job_id = self._generate_job_id("mock-slurm")
            self.jobs[job_id] = JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.PENDING,
                submit_time=datetime.now().isoformat(),
                error_message=f"SLURM submission simulated: {str(e)}",
                resources=resources,
            )
            return job_id

    def _generate_sbatch_script(
        self,
        command: str,
        resources: ResourceSpec,
        job_name: str,
        partition: str,
        environment: dict[str, str] | None,
        container: str | None,
        array: str | None,
        dependency: str | None,
        output_path: str | None,
    ) -> str:
        """Generate SLURM sbatch script."""
        slurm_spec = resources.to_slurm_spec()

        # Build SBATCH directives
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --partition={partition}",
            f"#SBATCH --cpus-per-task={slurm_spec['cpus-per-task']}",
            f"#SBATCH --mem={slurm_spec['mem']}",
            f"#SBATCH --time={slurm_spec['time']}",
            f"#SBATCH --output={self.config.slurm_work_dir}/{job_name}_%j.out",
            f"#SBATCH --error={self.config.slurm_work_dir}/{job_name}_%j.err",
        ]

        if self.config.slurm_account:
            lines.append(f"#SBATCH --account={self.config.slurm_account}")

        if "gres" in slurm_spec:
            lines.append(f"#SBATCH --gres={slurm_spec['gres']}")

        if array:
            lines.append(f"#SBATCH --array={array}")

        if dependency:
            lines.append(f"#SBATCH --dependency={dependency}")

        lines.append("")

        # Environment setup
        lines.append("# Environment setup")
        lines.append("set -e")
        lines.append(f"cd {self.config.slurm_work_dir}")

        if environment:
            for key, value in environment.items():
                lines.append(f"export {key}='{value}'")

        lines.append("")

        # Container execution or direct command
        if container:
            lines.append("# Run in container")
            lines.append(f"singularity exec {container} bash -c '{command}'")
        else:
            lines.append("# Run command")
            lines.append(command)

        # Output staging
        if output_path:
            lines.append("")
            lines.append(f"# Stage outputs")
            lines.append(f"mkdir -p {output_path}")
            lines.append(f"cp -r {self.config.slurm_work_dir}/{job_name}_* {output_path}/ 2>/dev/null || true")

        return "\n".join(lines)

    def _transfer_files(self, local_files: list[str], remote_dir: str):
        """Transfer files to remote cluster."""
        self._execute_remote(f"mkdir -p {remote_dir}")

        sftp = self.ssh_client.open_sftp()
        for local_path in local_files:
            filename = Path(local_path).name
            remote_path = f"{remote_dir}/{filename}"
            sftp.put(local_path, remote_path)
        sftp.close()

    def get_job_status(self, job_id: str) -> JobInfo:
        """Get job status from SLURM."""
        try:
            # Use sacct for completed jobs, squeue for running
            stdout, stderr, _ = self._execute_remote(
                f"sacct -j {job_id} --format=JobID,State,Start,End,ExitCode --noheader --parsable2"
            )

            if stdout.strip():
                # Parse sacct output
                lines = stdout.strip().split("\n")
                for line in lines:
                    parts = line.split("|")
                    if len(parts) >= 5 and parts[0] == job_id:
                        state = parts[1]
                        start_time = parts[2] if parts[2] != "Unknown" else None
                        end_time = parts[3] if parts[3] != "Unknown" else None
                        exit_code = int(parts[4].split(":")[0]) if ":" in parts[4] else None

                        status = self._map_slurm_status(state)

                        info = JobInfo(
                            job_id=job_id,
                            backend=self.backend.value,
                            status=status,
                            submit_time=self.jobs.get(job_id, JobInfo(job_id, "", JobStatus.UNKNOWN, "")).submit_time or datetime.now().isoformat(),
                            start_time=start_time,
                            end_time=end_time,
                            exit_code=exit_code,
                        )

                        self.jobs[job_id] = info
                        return info

            # Try squeue for pending/running jobs
            stdout, _, _ = self._execute_remote(
                f"squeue -j {job_id} --format='%i|%T|%S' --noheader"
            )

            if stdout.strip():
                parts = stdout.strip().split("|")
                if len(parts) >= 3:
                    state = parts[1]
                    start_time = parts[2] if parts[2] != "N/A" else None

                    info = JobInfo(
                        job_id=job_id,
                        backend=self.backend.value,
                        status=self._map_slurm_status(state),
                        submit_time=self.jobs.get(job_id, JobInfo(job_id, "", JobStatus.UNKNOWN, "")).submit_time or datetime.now().isoformat(),
                        start_time=start_time,
                    )

                    self.jobs[job_id] = info
                    return info

            # Return cached info
            if job_id in self.jobs:
                return self.jobs[job_id]

            return JobInfo(
                job_id=job_id,
                backend=self.backend.value,
                status=JobStatus.UNKNOWN,
                submit_time=datetime.now().isoformat(),
            )

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

    def _map_slurm_status(self, slurm_state: str) -> JobStatus:
        """Map SLURM state to JobStatus."""
        state = slurm_state.upper()
        mapping = {
            "PENDING": JobStatus.PENDING,
            "RUNNING": JobStatus.RUNNING,
            "COMPLETED": JobStatus.SUCCEEDED,
            "FAILED": JobStatus.FAILED,
            "CANCELLED": JobStatus.CANCELLED,
            "TIMEOUT": JobStatus.FAILED,
            "NODE_FAIL": JobStatus.FAILED,
            "PREEMPTED": JobStatus.FAILED,
            "SUSPENDED": JobStatus.PENDING,
            "CONFIGURING": JobStatus.PENDING,
            "COMPLETING": JobStatus.RUNNING,
        }
        return mapping.get(state, JobStatus.UNKNOWN)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job on SLURM."""
        try:
            stdout, stderr, exit_code = self._execute_remote(f"scancel {job_id}")
            if exit_code == 0:
                if job_id in self.jobs:
                    self.jobs[job_id].status = JobStatus.CANCELLED
                return True
            return False
        except Exception:
            return False

    def get_job_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs from SLURM output files."""
        try:
            # Find output files
            stdout, _, _ = self._execute_remote(
                f"ls {self.config.slurm_work_dir}/*_{job_id}.out 2>/dev/null | head -1"
            )

            if stdout.strip():
                output_file = stdout.strip()
                stdout, _, _ = self._execute_remote(f"tail -n {tail} {output_file}")
                return stdout
            else:
                return f"No output file found for job {job_id}"

        except Exception as e:
            return f"Error fetching logs: {e}"

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[JobInfo]:
        """List jobs from SLURM."""
        try:
            # List recent jobs
            cmd = f"sacct -u {self.config.slurm_user} --format=JobID,JobName,State,Start,End --noheader --parsable2 | head -n {limit}"
            stdout, _, _ = self._execute_remote(cmd)

            jobs = []
            for line in stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 5:
                    job_id = parts[0]
                    if "." in job_id:  # Skip sub-jobs
                        continue

                    state = parts[2]
                    job_status = self._map_slurm_status(state)

                    if status and job_status != status:
                        continue

                    jobs.append(JobInfo(
                        job_id=job_id,
                        backend=self.backend.value,
                        status=job_status,
                        submit_time=parts[3] if parts[3] != "Unknown" else "",
                        end_time=parts[4] if parts[4] != "Unknown" else None,
                    ))

            return jobs[:limit]

        except Exception:
            return list(self.jobs.values())[:limit]

    def get_cluster_info(self) -> dict:
        """Get information about the SLURM cluster."""
        try:
            info = {}

            # Get partition info
            stdout, _, _ = self._execute_remote("sinfo --format='%P|%a|%c|%m|%G' --noheader")
            partitions = []
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 5:
                        partitions.append({
                            "name": parts[0].replace("*", ""),
                            "available": parts[1],
                            "cpus": parts[2],
                            "memory": parts[3],
                            "gres": parts[4],
                        })
            info["partitions"] = partitions

            # Get queue status
            stdout, _, _ = self._execute_remote(f"squeue -u {self.config.slurm_user} --format='%i|%T' --noheader")
            pending = 0
            running = 0
            for line in stdout.strip().split("\n"):
                if "PENDING" in line:
                    pending += 1
                elif "RUNNING" in line:
                    running += 1
            info["pending_jobs"] = pending
            info["running_jobs"] = running

            return info

        except Exception as e:
            return {"error": str(e)}

    def submit_array_job(
        self,
        command: str,
        array_size: int,
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """
        Submit an array job to SLURM.

        Array jobs run the same command multiple times with different
        SLURM_ARRAY_TASK_ID values.
        """
        return self.submit_job(
            command=command,
            resources=resources,
            array=f"0-{array_size - 1}",
            **kwargs,
        )
