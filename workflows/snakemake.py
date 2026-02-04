"""
Snakemake workflow engine integration.

Snakemake is a workflow management system that uses Python-based rules for defining pipelines.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from .base import WorkflowEngine, WorkflowResult, WorkflowStatus


class SnakemakeEngine(WorkflowEngine):
    """Snakemake workflow engine client."""

    def __init__(self, workspace_dir: str):
        super().__init__(workspace_dir)
        self.smk_dir = self.workflows_dir / "snakemake"
        self.smk_dir.mkdir(parents=True, exist_ok=True)

    def check_installation(self) -> tuple[bool, str]:
        """Check if Snakemake is installed."""
        code, stdout, stderr = self._run_command(["snakemake", "--version"])
        if code == 0:
            version = stdout.strip()
            return True, f"Snakemake {version} is installed"
        return False, "Snakemake is not installed. Install with: pip install snakemake"

    def create_workflow(
        self,
        name: str,
        definition: str,
        params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Create a Snakemake workflow definition.

        Args:
            name: Workflow name
            definition: Snakemake workflow rules
            params: Optional config parameters

        Returns:
            WorkflowResult with the created workflow path
        """
        workflow_id = self._generate_workflow_id(name)
        workflow_dir = self.smk_dir / workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Write Snakefile
        snakefile = workflow_dir / "Snakefile"
        snakefile.write_text(definition, encoding="utf-8")

        # Write config file if provided
        if params:
            config_file = workflow_dir / "config.yaml"
            config_content = self._generate_yaml_config(params)
            config_file.write_text(config_content, encoding="utf-8")

        return WorkflowResult(
            success=True,
            message=f"Snakemake workflow created at {workflow_dir}",
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            outputs={"workflow_path": str(snakefile)},
        )

    def run_workflow(
        self,
        workflow_path: str,
        params: dict[str, Any] | None = None,
        resume: bool = False,
        dry_run: bool = False,
        cores: int = 4,
    ) -> WorkflowResult:
        """
        Execute a Snakemake workflow.

        Args:
            workflow_path: Path to Snakefile or workflow directory
            params: Runtime config parameters
            resume: Resume from last checkpoint (rerun-incomplete)
            dry_run: Just print what would be done
            cores: Number of CPU cores to use

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
            snakefile = workflow_path / "Snakefile"
        else:
            snakefile = workflow_path
            workflow_path = snakefile.parent

        if not snakefile.exists():
            return WorkflowResult(
                success=False,
                message=f"Snakefile not found: {snakefile}",
                status=WorkflowStatus.FAILED,
            )

        # Build command
        cmd = ["snakemake", "-s", str(snakefile), "--cores", str(cores)]

        if dry_run:
            cmd.append("--dry-run")

        if resume:
            cmd.append("--rerun-incomplete")

        # Add config parameters
        config_file = workflow_path / "config.yaml"
        if config_file.exists():
            cmd.extend(["--configfile", str(config_file)])

        if params:
            for key, value in params.items():
                cmd.extend(["--config", f"{key}={value}"])

        # Run workflow
        code, stdout, stderr = self._run_command(
            cmd,
            cwd=str(workflow_path),
            timeout=7200,  # 2 hour timeout
        )

        # Parse execution status
        if code == 0:
            status = WorkflowStatus.COMPLETED
            success = True
            message = "Workflow completed successfully" if not dry_run else "Dry run completed"
        else:
            status = WorkflowStatus.FAILED
            success = False
            message = f"Workflow failed with exit code {code}"

        # Collect outputs
        outputs = {}
        results_dir = workflow_path / "results"
        if results_dir.exists():
            outputs["results_dir"] = str(results_dir)
            output_files = list(results_dir.rglob("*"))[:20]
            outputs["output_files"] = [str(f) for f in output_files if f.is_file()]

        return WorkflowResult(
            success=success,
            message=message,
            workflow_id=workflow_path.name,
            status=status,
            outputs=outputs,
            logs=stdout + "\n" + stderr,
        )

    def get_status(self, workflow_id: str) -> WorkflowResult:
        """Get status of a Snakemake workflow."""
        workflow_dir = self.smk_dir / workflow_id

        if not workflow_dir.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        # Check for .snakemake directory
        smk_meta = workflow_dir / ".snakemake"

        status = WorkflowStatus.PENDING
        message = "Workflow status unknown"

        if smk_meta.exists():
            # Check for incomplete markers
            incomplete_dir = smk_meta / "incomplete"
            if incomplete_dir.exists() and list(incomplete_dir.iterdir()):
                status = WorkflowStatus.RUNNING
                message = "Workflow is running or has incomplete jobs"
            else:
                # Assume completed if .snakemake exists but no incomplete
                status = WorkflowStatus.COMPLETED
                message = "Workflow appears completed"

        return WorkflowResult(
            success=True,
            message=message,
            workflow_id=workflow_id,
            status=status,
        )

    def get_outputs(self, workflow_id: str) -> WorkflowResult:
        """Get outputs from a completed Snakemake workflow."""
        workflow_dir = self.smk_dir / workflow_id

        if not workflow_dir.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        outputs = {}

        # Look for results directory
        results_dir = workflow_dir / "results"
        if results_dir.exists():
            outputs["results_dir"] = str(results_dir)
            output_files = list(results_dir.rglob("*"))
            outputs["output_files"] = [str(f) for f in output_files if f.is_file()][:50]

        # Look for log files
        logs_dir = workflow_dir / "logs"
        logs = ""
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            if log_files:
                # Read last log file
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

    def _generate_yaml_config(self, params: dict[str, Any]) -> str:
        """Generate YAML config file content."""
        lines = ["# Snakemake configuration"]
        for key, value in params.items():
            if isinstance(value, str):
                lines.append(f'{key}: "{value}"')
            elif isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f'  - "{item}"' if isinstance(item, str) else f"  - {item}")
            elif isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f'  {k}: "{v}"' if isinstance(v, str) else f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def list_workflows(self) -> list[dict]:
        """List all Snakemake workflows in the workspace."""
        workflows = []
        for d in self.smk_dir.iterdir():
            if d.is_dir() and (d / "Snakefile").exists():
                workflows.append({
                    "id": d.name,
                    "path": str(d),
                    "snakefile": str(d / "Snakefile"),
                })
        return workflows

    def visualize_dag(self, workflow_id: str) -> WorkflowResult:
        """Generate a DAG visualization of the workflow."""
        workflow_dir = self.smk_dir / workflow_id
        snakefile = workflow_dir / "Snakefile"

        if not snakefile.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        dag_file = workflow_dir / "dag.svg"
        cmd = ["snakemake", "-s", str(snakefile), "--dag", "|", "dot", "-Tsvg", ">", str(dag_file)]

        # This needs shell=True for piping
        code, stdout, stderr = self._run_command(
            ["snakemake", "-s", str(snakefile), "--dag"],
            cwd=str(workflow_dir),
        )

        if code == 0:
            return WorkflowResult(
                success=True,
                message=f"DAG generated (DOT format)",
                workflow_id=workflow_id,
                outputs={"dag_dot": stdout},
            )
        else:
            return WorkflowResult(
                success=False,
                message=f"Failed to generate DAG: {stderr}",
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
            )


# Common Snakemake workflow templates
SNAKEMAKE_TEMPLATES = {
    "rnaseq_basic": '''
# RNA-seq analysis pipeline
configfile: "config.yaml"

SAMPLES = config.get("samples", [])
GENOME = config.get("genome", "reference/genome.fa")
GTF = config.get("gtf", "reference/genes.gtf")

rule all:
    input:
        expand("results/counts/{sample}_counts.txt", sample=SAMPLES),
        expand("results/fastqc/{sample}_fastqc.html", sample=SAMPLES)

rule fastqc:
    input:
        r1="data/{sample}_1.fastq.gz",
        r2="data/{sample}_2.fastq.gz"
    output:
        html="results/fastqc/{sample}_fastqc.html",
        zip="results/fastqc/{sample}_fastqc.zip"
    threads: 2
    shell:
        "fastqc -t {threads} {input.r1} {input.r2} -o results/fastqc/"

rule star_index:
    input:
        genome=GENOME,
        gtf=GTF
    output:
        directory("reference/star_index")
    threads: 4
    shell:
        """
        mkdir -p {output}
        STAR --runMode genomeGenerate \\
            --genomeDir {output} \\
            --genomeFastaFiles {input.genome} \\
            --sjdbGTFfile {input.gtf} \\
            --runThreadN {threads}
        """

rule star_align:
    input:
        r1="data/{sample}_1.fastq.gz",
        r2="data/{sample}_2.fastq.gz",
        index="reference/star_index"
    output:
        bam="results/aligned/{sample}.Aligned.sortedByCoord.out.bam"
    threads: 4
    shell:
        """
        STAR --genomeDir {input.index} \\
            --readFilesIn {input.r1} {input.r2} \\
            --readFilesCommand zcat \\
            --outFileNamePrefix results/aligned/{wildcards.sample}. \\
            --outSAMtype BAM SortedByCoordinate \\
            --runThreadN {threads}
        """

rule featurecounts:
    input:
        bam="results/aligned/{sample}.Aligned.sortedByCoord.out.bam",
        gtf=GTF
    output:
        counts="results/counts/{sample}_counts.txt"
    threads: 4
    shell:
        "featureCounts -T {threads} -p -a {input.gtf} -o {output.counts} {input.bam}"
''',

    "variant_calling": '''
# Variant calling pipeline
configfile: "config.yaml"

SAMPLES = config.get("samples", [])
REFERENCE = config.get("reference", "reference/genome.fa")

rule all:
    input:
        expand("results/variants/{sample}.vcf.gz", sample=SAMPLES)

rule bwa_index:
    input:
        reference=REFERENCE
    output:
        multiext(REFERENCE, ".amb", ".ann", ".bwt", ".pac", ".sa")
    shell:
        "bwa index {input.reference}"

rule bwa_mem:
    input:
        r1="data/{sample}_1.fastq.gz",
        r2="data/{sample}_2.fastq.gz",
        reference=REFERENCE,
        index=multiext(REFERENCE, ".amb", ".ann", ".bwt", ".pac", ".sa")
    output:
        bam="results/aligned/{sample}.sorted.bam",
        bai="results/aligned/{sample}.sorted.bam.bai"
    threads: 4
    shell:
        """
        bwa mem -t {threads} -R "@RG\\tID:{wildcards.sample}\\tSM:{wildcards.sample}\\tPL:ILLUMINA" \\
            {input.reference} {input.r1} {input.r2} | \\
            samtools sort -@ {threads} -o {output.bam} -
        samtools index {output.bam}
        """

rule mark_duplicates:
    input:
        bam="results/aligned/{sample}.sorted.bam"
    output:
        bam="results/dedup/{sample}.dedup.bam",
        bai="results/dedup/{sample}.dedup.bam.bai",
        metrics="results/dedup/{sample}.metrics.txt"
    shell:
        """
        gatk MarkDuplicates -I {input.bam} -O {output.bam} -M {output.metrics}
        samtools index {output.bam}
        """

rule haplotype_caller:
    input:
        bam="results/dedup/{sample}.dedup.bam",
        bai="results/dedup/{sample}.dedup.bam.bai",
        reference=REFERENCE
    output:
        vcf="results/variants/{sample}.vcf.gz"
    shell:
        "gatk HaplotypeCaller -R {input.reference} -I {input.bam} -O {output.vcf}"
''',
}
