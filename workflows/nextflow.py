"""
Nextflow workflow engine integration.

Nextflow enables scalable and reproducible scientific workflows using software containers.
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .base import WorkflowEngine, WorkflowResult, WorkflowStatus


class NextflowEngine(WorkflowEngine):
    """Nextflow workflow engine client."""

    def __init__(self, workspace_dir: str):
        super().__init__(workspace_dir)
        self.nf_dir = self.workflows_dir / "nextflow"
        self.nf_dir.mkdir(parents=True, exist_ok=True)

    def check_installation(self) -> tuple[bool, str]:
        """Check if Nextflow is installed."""
        code, stdout, stderr = self._run_command(["nextflow", "-version"])
        if code == 0:
            # Extract version from output
            version_match = re.search(r"version (\d+\.\d+\.\d+)", stdout)
            version = version_match.group(1) if version_match else "unknown"
            return True, f"Nextflow {version} is installed"
        return False, "Nextflow is not installed. Install with: curl -s https://get.nextflow.io | bash"

    def create_workflow(
        self,
        name: str,
        definition: str,
        params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Create a Nextflow workflow definition.

        Args:
            name: Workflow name
            definition: Nextflow DSL2 workflow code
            params: Optional default parameters

        Returns:
            WorkflowResult with the created workflow path
        """
        workflow_id = self._generate_workflow_id(name)
        workflow_dir = self.nf_dir / workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Write main workflow file
        main_nf = workflow_dir / "main.nf"
        main_nf.write_text(definition, encoding="utf-8")

        # Write params file if provided
        if params:
            params_file = workflow_dir / "nextflow.config"
            params_config = self._generate_config(params)
            params_file.write_text(params_config, encoding="utf-8")

        return WorkflowResult(
            success=True,
            message=f"Nextflow workflow created at {workflow_dir}",
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            outputs={"workflow_path": str(main_nf)},
        )

    def run_workflow(
        self,
        workflow_path: str,
        params: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> WorkflowResult:
        """
        Execute a Nextflow workflow.

        Args:
            workflow_path: Path to main.nf or workflow directory
            params: Runtime parameters
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
            main_nf = workflow_path / "main.nf"
        else:
            main_nf = workflow_path
            workflow_path = main_nf.parent

        if not main_nf.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow file not found: {main_nf}",
                status=WorkflowStatus.FAILED,
            )

        # Build command
        cmd = ["nextflow", "run", str(main_nf)]

        if resume:
            cmd.append("-resume")

        # Add parameters
        if params:
            for key, value in params.items():
                cmd.extend([f"--{key}", str(value)])

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
            message = "Workflow completed successfully"
        else:
            status = WorkflowStatus.FAILED
            success = False
            message = f"Workflow failed with exit code {code}"

        # Look for output directory
        outputs = {}
        results_dir = workflow_path / "results"
        if results_dir.exists():
            outputs["results_dir"] = str(results_dir)
            # List output files
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
        """Get status of a Nextflow workflow."""
        workflow_dir = self.nf_dir / workflow_id

        if not workflow_dir.exists():
            return WorkflowResult(
                success=False,
                message=f"Workflow {workflow_id} not found",
                status=WorkflowStatus.FAILED,
            )

        # Check for Nextflow work directory and trace files
        work_dir = workflow_dir / "work"
        trace_file = workflow_dir / ".nextflow" / "history"

        status = WorkflowStatus.PENDING
        message = "Workflow status unknown"

        if trace_file.exists():
            # Parse trace to get status
            trace_content = trace_file.read_text()
            if "OK" in trace_content:
                status = WorkflowStatus.COMPLETED
                message = "Workflow completed"
            elif "ERR" in trace_content:
                status = WorkflowStatus.FAILED
                message = "Workflow failed"
            else:
                status = WorkflowStatus.RUNNING
                message = "Workflow is running"
        elif work_dir.exists():
            status = WorkflowStatus.RUNNING
            message = "Workflow is running"

        return WorkflowResult(
            success=True,
            message=message,
            workflow_id=workflow_id,
            status=status,
        )

    def get_outputs(self, workflow_id: str) -> WorkflowResult:
        """Get outputs from a completed Nextflow workflow."""
        workflow_dir = self.nf_dir / workflow_id

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

        # Look for reports
        reports_dir = workflow_dir / "reports"
        if reports_dir.exists():
            report_files = list(reports_dir.glob("*"))
            outputs["reports"] = [str(f) for f in report_files]

        # Get execution log
        log_file = workflow_dir / ".nextflow.log"
        logs = ""
        if log_file.exists():
            logs = log_file.read_text()[-5000:]  # Last 5000 chars

        return WorkflowResult(
            success=True,
            message=f"Found {len(outputs.get('output_files', []))} output files",
            workflow_id=workflow_id,
            status=WorkflowStatus.COMPLETED,
            outputs=outputs,
            logs=logs,
        )

    def _generate_config(self, params: dict[str, Any]) -> str:
        """Generate Nextflow config file content."""
        lines = ["// Nextflow configuration", "params {"]
        for key, value in params.items():
            if isinstance(value, str):
                lines.append(f'    {key} = "{value}"')
            elif isinstance(value, bool):
                lines.append(f"    {key} = {str(value).lower()}")
            else:
                lines.append(f"    {key} = {value}")
        lines.append("}")
        return "\n".join(lines)

    def list_workflows(self) -> list[dict]:
        """List all Nextflow workflows in the workspace."""
        workflows = []
        for d in self.nf_dir.iterdir():
            if d.is_dir() and (d / "main.nf").exists():
                workflows.append({
                    "id": d.name,
                    "path": str(d),
                    "main_nf": str(d / "main.nf"),
                })
        return workflows


# Common Nextflow workflow templates
NEXTFLOW_TEMPLATES = {
    "rnaseq_basic": '''
#!/usr/bin/env nextflow
nextflow.enable.dsl=2

// RNA-seq basic analysis pipeline
params.reads = "data/*_{1,2}.fastq.gz"
params.genome = "reference/genome.fa"
params.gtf = "reference/genes.gtf"
params.outdir = "results"

process FASTQC {
    publishDir "${params.outdir}/fastqc", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)

    output:
    path "*.html"
    path "*.zip"

    script:
    """
    fastqc -t 2 ${reads}
    """
}

process STAR_INDEX {
    input:
    path genome
    path gtf

    output:
    path "star_index"

    script:
    """
    mkdir star_index
    STAR --runMode genomeGenerate \\
        --genomeDir star_index \\
        --genomeFastaFiles ${genome} \\
        --sjdbGTFfile ${gtf} \\
        --runThreadN 4
    """
}

process STAR_ALIGN {
    publishDir "${params.outdir}/aligned", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    path index

    output:
    tuple val(sample_id), path("${sample_id}.Aligned.sortedByCoord.out.bam")

    script:
    """
    STAR --genomeDir ${index} \\
        --readFilesIn ${reads} \\
        --readFilesCommand zcat \\
        --outFileNamePrefix ${sample_id}. \\
        --outSAMtype BAM SortedByCoordinate \\
        --runThreadN 4
    """
}

process FEATURECOUNTS {
    publishDir "${params.outdir}/counts", mode: 'copy'

    input:
    tuple val(sample_id), path(bam)
    path gtf

    output:
    path "${sample_id}_counts.txt"

    script:
    """
    featureCounts -T 4 -p -a ${gtf} -o ${sample_id}_counts.txt ${bam}
    """
}

workflow {
    // Create channel from read pairs
    read_pairs = Channel.fromFilePairs(params.reads)

    // Run FastQC
    FASTQC(read_pairs)

    // Build STAR index
    genome = file(params.genome)
    gtf = file(params.gtf)
    star_index = STAR_INDEX(genome, gtf)

    // Align reads
    aligned = STAR_ALIGN(read_pairs, star_index)

    // Count features
    FEATURECOUNTS(aligned, gtf)
}
''',

    "variant_calling": '''
#!/usr/bin/env nextflow
nextflow.enable.dsl=2

// Variant calling pipeline
params.reads = "data/*_{1,2}.fastq.gz"
params.reference = "reference/genome.fa"
params.known_sites = "reference/known_sites.vcf.gz"
params.outdir = "results"

process BWA_INDEX {
    input:
    path reference

    output:
    path "${reference}*"

    script:
    """
    bwa index ${reference}
    """
}

process BWA_MEM {
    publishDir "${params.outdir}/aligned", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    path reference
    path index

    output:
    tuple val(sample_id), path("${sample_id}.sorted.bam"), path("${sample_id}.sorted.bam.bai")

    script:
    """
    bwa mem -t 4 -R "@RG\\tID:${sample_id}\\tSM:${sample_id}\\tPL:ILLUMINA" \\
        ${reference} ${reads} | \\
        samtools sort -@ 4 -o ${sample_id}.sorted.bam -
    samtools index ${sample_id}.sorted.bam
    """
}

process MARK_DUPLICATES {
    publishDir "${params.outdir}/dedup", mode: 'copy'

    input:
    tuple val(sample_id), path(bam), path(bai)

    output:
    tuple val(sample_id), path("${sample_id}.dedup.bam"), path("${sample_id}.dedup.bam.bai")

    script:
    """
    gatk MarkDuplicates \\
        -I ${bam} \\
        -O ${sample_id}.dedup.bam \\
        -M ${sample_id}.metrics.txt
    samtools index ${sample_id}.dedup.bam
    """
}

process HAPLOTYPE_CALLER {
    publishDir "${params.outdir}/variants", mode: 'copy'

    input:
    tuple val(sample_id), path(bam), path(bai)
    path reference

    output:
    path "${sample_id}.vcf.gz"

    script:
    """
    gatk HaplotypeCaller \\
        -R ${reference} \\
        -I ${bam} \\
        -O ${sample_id}.vcf.gz
    """
}

workflow {
    // Create channels
    read_pairs = Channel.fromFilePairs(params.reads)
    reference = file(params.reference)

    // Index reference
    bwa_index = BWA_INDEX(reference)

    // Align reads
    aligned = BWA_MEM(read_pairs, reference, bwa_index)

    // Mark duplicates
    deduped = MARK_DUPLICATES(aligned)

    // Call variants
    HAPLOTYPE_CALLER(deduped, reference)
}
''',
}
