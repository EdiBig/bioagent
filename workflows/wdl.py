"""
WDL (Workflow Description Language) workflow engine integration.

WDL is designed for describing data processing workflows with a focus on
portability and reproducibility, commonly used with Cromwell execution engine.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from .base import WorkflowEngine, WorkflowResult, WorkflowStatus


class WDLEngine(WorkflowEngine):
    """WDL/Cromwell workflow engine client."""

    def __init__(self, workspace_dir: str, cromwell_jar: str | None = None):
        super().__init__(workspace_dir)
        self.wdl_dir = self.workflows_dir / "wdl"
        self.wdl_dir.mkdir(parents=True, exist_ok=True)
        self.cromwell_jar = cromwell_jar
        self._miniwdl_cmd = None

    def _get_miniwdl_command(self) -> list[str]:
        """Get the command to run miniwdl."""
        if self._miniwdl_cmd:
            return self._miniwdl_cmd

        import os
        import subprocess

        # On Windows, miniwdl requires WSL (uses fcntl which is Unix-only)
        if os.name == 'nt':
            try:
                result = subprocess.run(
                    ["wsl", "-d", "Ubuntu", "-e", "bash", "-c", 'export PATH="$HOME/.local/bin:$PATH" && miniwdl --version'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    self._miniwdl_cmd = ["wsl", "-d", "Ubuntu", "-e", "bash", "-c"]
                    return self._miniwdl_cmd
            except:
                pass

        # Try direct miniwdl command (Linux/macOS)
        self._miniwdl_cmd = ["miniwdl"]
        return self._miniwdl_cmd

    def check_installation(self) -> tuple[bool, str]:
        """Check if Cromwell/WDL tools are available."""
        import os
        import subprocess

        # On Windows, check WSL for miniwdl
        if os.name == 'nt':
            try:
                result = subprocess.run(
                    ["wsl", "-d", "Ubuntu", "-e", "bash", "-c", 'export PATH="$HOME/.local/bin:$PATH" && miniwdl --version'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    return True, f"{version} is installed (via WSL)"
            except:
                pass
            return False, "miniwdl not found in WSL. Install with: wsl pip3 install --user miniwdl"

        # Check for miniwdl on Unix
        code, stdout, stderr = self._run_command(["miniwdl", "--version"])
        if code == 0:
            version = stdout.strip()
            return True, f"{version} is installed"

        # Check for cromwell jar
        if self.cromwell_jar and Path(self.cromwell_jar).exists():
            return True, f"Cromwell JAR found at {self.cromwell_jar}"

        return False, "WDL runtime not found. Install with: pip install miniwdl"

    def create_workflow(
        self,
        name: str,
        definition: str,
        params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Create a WDL workflow definition.

        Args:
            name: Workflow name
            definition: WDL workflow code
            params: Optional input parameters

        Returns:
            WorkflowResult with the created workflow path
        """
        workflow_id = self._generate_workflow_id(name)
        workflow_dir = self.wdl_dir / workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Write main WDL file
        main_wdl = workflow_dir / "main.wdl"
        main_wdl.write_text(definition, encoding="utf-8")

        # Write inputs JSON if provided
        if params:
            inputs_file = workflow_dir / "inputs.json"
            inputs_file.write_text(json.dumps(params, indent=2), encoding="utf-8")

        return WorkflowResult(
            success=True,
            message=f"WDL workflow created at {workflow_dir}",
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            outputs={"workflow_path": str(main_wdl)},
        )

    def _convert_to_wsl_path(self, windows_path: str) -> str:
        """Convert Windows path to WSL path."""
        path = str(windows_path).replace("\\", "/")
        if len(path) >= 2 and path[1] == ":":
            drive = path[0].lower()
            path = f"/mnt/{drive}{path[2:]}"
        return path

    def _run_miniwdl_command(self, args: list[str], cwd: str | None = None, timeout: int = 7200) -> tuple[int, str, str]:
        """Run miniwdl command, using WSL on Windows."""
        import os
        import subprocess

        if os.name == 'nt':
            # Convert paths to WSL format
            wsl_args = []
            for arg in args:
                # Check if it looks like a Windows path
                if len(arg) >= 2 and arg[1] == ":":
                    wsl_args.append(self._convert_to_wsl_path(arg))
                elif "\\" in arg:
                    wsl_args.append(self._convert_to_wsl_path(arg))
                else:
                    wsl_args.append(arg)

            wsl_cwd = self._convert_to_wsl_path(cwd) if cwd else None
            cd_cmd = f"cd '{wsl_cwd}' && " if wsl_cwd else ""
            cmd_str = f'export PATH="$HOME/.local/bin:$PATH" && {cd_cmd}miniwdl {" ".join(wsl_args)}'

            try:
                result = subprocess.run(
                    ["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd_str],
                    capture_output=True, text=True, timeout=timeout
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return -1, "", f"Command timed out after {timeout} seconds"
            except Exception as e:
                return -1, "", str(e)
        else:
            return self._run_command(["miniwdl"] + args, cwd=cwd, timeout=timeout)

    def validate_workflow(self, workflow_path: str) -> WorkflowResult:
        """Validate a WDL workflow syntax."""
        workflow_path = Path(workflow_path)
        if workflow_path.is_dir():
            wdl_file = workflow_path / "main.wdl"
        else:
            wdl_file = workflow_path

        if not wdl_file.exists():
            return WorkflowResult(
                success=False,
                message=f"WDL file not found: {wdl_file}",
                status=WorkflowStatus.FAILED,
            )

        # Try miniwdl check
        code, stdout, stderr = self._run_miniwdl_command(["check", str(wdl_file)], cwd=str(wdl_file.parent))

        if code == 0:
            return WorkflowResult(
                success=True,
                message="WDL validation passed",
                outputs={"validation": stdout},
            )
        else:
            return WorkflowResult(
                success=False,
                message=f"WDL validation failed:\n{stderr}",
                status=WorkflowStatus.FAILED,
            )

    def run_workflow(
        self,
        workflow_path: str,
        params: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> WorkflowResult:
        """
        Execute a WDL workflow using miniwdl.

        Args:
            workflow_path: Path to WDL file or workflow directory
            params: Input parameters (overrides inputs.json)
            resume: Resume from last checkpoint

        Returns:
            WorkflowResult with execution status
        """
        # Check installation first
        installed, msg = self.check_installation()
        if not installed:
            return WorkflowResult(
                success=False,
                message=msg,
                status=WorkflowStatus.FAILED,
            )

        workflow_path = Path(workflow_path)
        if workflow_path.is_dir():
            wdl_file = workflow_path / "main.wdl"
        else:
            wdl_file = workflow_path
            workflow_path = wdl_file.parent

        if not wdl_file.exists():
            return WorkflowResult(
                success=False,
                message=f"WDL file not found: {wdl_file}",
                status=WorkflowStatus.FAILED,
            )

        # Build miniwdl command arguments
        args = ["run", str(wdl_file)]

        # Add inputs file if it exists
        inputs_file = workflow_path / "inputs.json"
        if inputs_file.exists():
            args.extend(["-i", str(inputs_file)])

        # Add command-line inputs
        if params:
            for key, value in params.items():
                if isinstance(value, (list, dict)):
                    args.append(f"{key}={json.dumps(value)}")
                else:
                    args.append(f"{key}={value}")

        # Set output directory
        output_dir = workflow_path / "output"
        args.extend(["-d", str(output_dir)])

        # Run workflow using WSL on Windows
        code, stdout, stderr = self._run_miniwdl_command(
            args,
            cwd=str(workflow_path),
            timeout=7200,  # 2 hour timeout
        )

        # Parse execution status
        if code == 0:
            status = WorkflowStatus.COMPLETED
            success = True
            message = "Workflow completed successfully"
        else:
            status = WorkflowStatus.FAILED
            success = False
            message = f"Workflow failed with exit code {code}"

        # Collect outputs
        outputs = {}
        if output_dir.exists():
            outputs["output_dir"] = str(output_dir)
            # Look for outputs.json
            outputs_json = output_dir / "outputs.json"
            if outputs_json.exists():
                try:
                    outputs["workflow_outputs"] = json.loads(outputs_json.read_text())
                except json.JSONDecodeError:
                    pass

        return WorkflowResult(
            success=success,
            message=message,
            workflow_id=workflow_path.name,
            status=status,
            outputs=outputs,
            logs=stdout + "\n" + stderr,
        )

    def get_status(self, workflow_id: str) -> WorkflowResult:
        """Get status of a WDL workflow."""
        workflow_dir = self.wdl_dir / workflow_id

        if not workflow_dir.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        # Check for output directory
        output_dir = workflow_dir / "output"

        status = WorkflowStatus.PENDING
        message = "Workflow status unknown"

        if output_dir.exists():
            outputs_json = output_dir / "outputs.json"
            if outputs_json.exists():
                status = WorkflowStatus.COMPLETED
                message = "Workflow completed"
            else:
                status = WorkflowStatus.RUNNING
                message = "Workflow is running"

        return WorkflowResult(
            success=True,
            message=message,
            workflow_id=workflow_id,
            status=status,
        )

    def get_outputs(self, workflow_id: str) -> WorkflowResult:
        """Get outputs from a completed WDL workflow."""
        workflow_dir = self.wdl_dir / workflow_id

        if not workflow_dir.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        outputs = {}
        output_dir = workflow_dir / "output"

        if output_dir.exists():
            outputs["output_dir"] = str(output_dir)

            # Read outputs.json
            outputs_json = output_dir / "outputs.json"
            if outputs_json.exists():
                try:
                    outputs["workflow_outputs"] = json.loads(outputs_json.read_text())
                except json.JSONDecodeError:
                    pass

            # List output files
            output_files = list(output_dir.rglob("*"))
            outputs["output_files"] = [str(f) for f in output_files if f.is_file()][:50]

        # Get logs
        logs = ""
        log_dir = workflow_dir / "output" / "wdl"
        if log_dir.exists():
            log_files = list(log_dir.rglob("*.log"))
            if log_files:
                latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
                logs = latest_log.read_text()[-5000:]

        return WorkflowResult(
            success=True,
            message=f"Found {len(outputs.get('output_files', []))} output files",
            workflow_id=workflow_id,
            status=WorkflowStatus.COMPLETED,
            outputs=outputs,
            logs=logs,
        )

    def list_workflows(self) -> list[dict]:
        """List all WDL workflows in the workspace."""
        workflows = []
        for d in self.wdl_dir.iterdir():
            if d.is_dir() and (d / "main.wdl").exists():
                workflows.append({
                    "id": d.name,
                    "path": str(d),
                    "wdl_file": str(d / "main.wdl"),
                })
        return workflows


# Common WDL workflow templates
WDL_TEMPLATES = {
    "rnaseq_basic": '''
version 1.0

# RNA-seq analysis workflow

workflow RNAseqPipeline {
    input {
        Array[File] reads_1
        Array[File] reads_2
        Array[String] sample_names
        File genome_fasta
        File gtf_annotation
    }

    scatter (i in range(length(sample_names))) {
        call FastQC {
            input:
                reads_1 = reads_1[i],
                reads_2 = reads_2[i],
                sample_name = sample_names[i]
        }

        call STARAlign {
            input:
                reads_1 = reads_1[i],
                reads_2 = reads_2[i],
                sample_name = sample_names[i],
                genome_fasta = genome_fasta,
                gtf = gtf_annotation
        }

        call FeatureCounts {
            input:
                bam = STARAlign.aligned_bam,
                gtf = gtf_annotation,
                sample_name = sample_names[i]
        }
    }

    output {
        Array[File] fastqc_reports = FastQC.report_html
        Array[File] aligned_bams = STARAlign.aligned_bam
        Array[File] count_files = FeatureCounts.counts
    }
}

task FastQC {
    input {
        File reads_1
        File reads_2
        String sample_name
    }

    command <<<
        fastqc -t 2 ~{reads_1} ~{reads_2} -o .
    >>>

    output {
        File report_html = "~{sample_name}_fastqc.html"
        File report_zip = "~{sample_name}_fastqc.zip"
    }

    runtime {
        docker: "biocontainers/fastqc:v0.11.9"
        cpu: 2
        memory: "4 GB"
    }
}

task STARAlign {
    input {
        File reads_1
        File reads_2
        String sample_name
        File genome_fasta
        File gtf
    }

    command <<<
        # Build index and align
        mkdir star_index
        STAR --runMode genomeGenerate \
            --genomeDir star_index \
            --genomeFastaFiles ~{genome_fasta} \
            --sjdbGTFfile ~{gtf} \
            --runThreadN 4

        STAR --genomeDir star_index \
            --readFilesIn ~{reads_1} ~{reads_2} \
            --readFilesCommand zcat \
            --outFileNamePrefix ~{sample_name}. \
            --outSAMtype BAM SortedByCoordinate \
            --runThreadN 4
    >>>

    output {
        File aligned_bam = "~{sample_name}.Aligned.sortedByCoord.out.bam"
    }

    runtime {
        docker: "quay.io/biocontainers/star:2.7.10a"
        cpu: 4
        memory: "32 GB"
    }
}

task FeatureCounts {
    input {
        File bam
        File gtf
        String sample_name
    }

    command <<<
        featureCounts -T 4 -p -a ~{gtf} -o ~{sample_name}_counts.txt ~{bam}
    >>>

    output {
        File counts = "~{sample_name}_counts.txt"
    }

    runtime {
        docker: "quay.io/biocontainers/subread:2.0.1"
        cpu: 4
        memory: "8 GB"
    }
}
''',

    "variant_calling": '''
version 1.0

# Variant calling workflow

workflow VariantCallingPipeline {
    input {
        Array[File] reads_1
        Array[File] reads_2
        Array[String] sample_names
        File reference_fasta
        File reference_fasta_index
        File reference_dict
    }

    scatter (i in range(length(sample_names))) {
        call BWAAlign {
            input:
                reads_1 = reads_1[i],
                reads_2 = reads_2[i],
                sample_name = sample_names[i],
                reference = reference_fasta
        }

        call MarkDuplicates {
            input:
                bam = BWAAlign.aligned_bam,
                sample_name = sample_names[i]
        }

        call HaplotypeCaller {
            input:
                bam = MarkDuplicates.dedup_bam,
                bam_index = MarkDuplicates.dedup_bam_index,
                reference = reference_fasta,
                reference_index = reference_fasta_index,
                reference_dict = reference_dict,
                sample_name = sample_names[i]
        }
    }

    output {
        Array[File] vcf_files = HaplotypeCaller.vcf
    }
}

task BWAAlign {
    input {
        File reads_1
        File reads_2
        String sample_name
        File reference
    }

    command <<<
        bwa index ~{reference}
        bwa mem -t 4 -R "@RG\\tID:~{sample_name}\\tSM:~{sample_name}\\tPL:ILLUMINA" \
            ~{reference} ~{reads_1} ~{reads_2} | \
            samtools sort -@ 4 -o ~{sample_name}.sorted.bam -
        samtools index ~{sample_name}.sorted.bam
    >>>

    output {
        File aligned_bam = "~{sample_name}.sorted.bam"
        File aligned_bam_index = "~{sample_name}.sorted.bam.bai"
    }

    runtime {
        docker: "biocontainers/bwa:v0.7.17"
        cpu: 4
        memory: "16 GB"
    }
}

task MarkDuplicates {
    input {
        File bam
        String sample_name
    }

    command <<<
        gatk MarkDuplicates \
            -I ~{bam} \
            -O ~{sample_name}.dedup.bam \
            -M ~{sample_name}.metrics.txt
        samtools index ~{sample_name}.dedup.bam
    >>>

    output {
        File dedup_bam = "~{sample_name}.dedup.bam"
        File dedup_bam_index = "~{sample_name}.dedup.bam.bai"
        File metrics = "~{sample_name}.metrics.txt"
    }

    runtime {
        docker: "broadinstitute/gatk:4.3.0.0"
        cpu: 2
        memory: "8 GB"
    }
}

task HaplotypeCaller {
    input {
        File bam
        File bam_index
        File reference
        File reference_index
        File reference_dict
        String sample_name
    }

    command <<<
        gatk HaplotypeCaller \
            -R ~{reference} \
            -I ~{bam} \
            -O ~{sample_name}.vcf.gz
    >>>

    output {
        File vcf = "~{sample_name}.vcf.gz"
    }

    runtime {
        docker: "broadinstitute/gatk:4.3.0.0"
        cpu: 4
        memory: "16 GB"
    }
}
''',
}
