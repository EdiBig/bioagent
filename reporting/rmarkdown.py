"""
R Markdown report generation.

Creates reproducible R Markdown documents for bioinformatics analyses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RMarkdownChunk:
    """An R code chunk."""

    code: str
    name: str = ""
    options: dict = field(default_factory=dict)

    def to_string(self) -> str:
        """Convert to R Markdown chunk format."""
        opts = ", ".join([f"{k}={v}" for k, v in self.options.items()])
        header = f"```{{r {self.name}" if self.name else "```{r"
        if opts:
            header += f", {opts}"
        header += "}"

        return f"{header}\n{self.code}\n```"


class RMarkdownGenerator:
    """
    Generate R Markdown documents for analysis reports.

    Creates structured documents with:
    - YAML header
    - Setup chunks
    - Analysis code
    - Visualizations
    - Results tables
    """

    def __init__(
        self,
        title: str = "BioAgent Analysis Report",
        author: str = "BioAgent",
        output_format: str = "html_document",
    ):
        """
        Initialize the R Markdown generator.

        Args:
            title: Document title
            author: Author name
            output_format: Output format (html_document, pdf_document, etc.)
        """
        self.title = title
        self.author = author
        self.output_format = output_format
        self.content: list[str] = []

        # Build YAML header
        self._add_yaml_header()

    def _add_yaml_header(self):
        """Add YAML header to document."""
        yaml = f"""---
title: "{self.title}"
author: "{self.author}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
output:
  {self.output_format}:
    toc: true
    toc_depth: 3
    toc_float: true
    code_folding: hide
    theme: flatly
    highlight: tango
---
"""
        self.content.append(yaml)

    def add_markdown(self, text: str) -> "RMarkdownGenerator":
        """Add markdown text."""
        self.content.append(text + "\n")
        return self

    def add_chunk(
        self,
        code: str,
        name: str = "",
        echo: bool = True,
        eval: bool = True,
        message: bool = False,
        warning: bool = False,
        fig_width: float | None = None,
        fig_height: float | None = None,
        **kwargs,
    ) -> "RMarkdownGenerator":
        """
        Add an R code chunk.

        Args:
            code: R code
            name: Chunk name
            echo: Show code
            eval: Evaluate code
            message: Show messages
            warning: Show warnings
            fig_width: Figure width
            fig_height: Figure height
            **kwargs: Additional chunk options
        """
        options = {
            "echo": str(echo).upper(),
            "eval": str(eval).upper(),
            "message": str(message).upper(),
            "warning": str(warning).upper(),
        }

        if fig_width:
            options["fig.width"] = fig_width
        if fig_height:
            options["fig.height"] = fig_height

        options.update(kwargs)

        chunk = RMarkdownChunk(code=code, name=name, options=options)
        self.content.append(chunk.to_string() + "\n")
        return self

    def add_setup_chunk(self) -> "RMarkdownGenerator":
        """Add standard setup chunk."""
        code = """# Load required packages
library(tidyverse)
library(DT)
library(plotly)
library(knitr)

# Set global options
knitr::opts_chunk$set(
  echo = TRUE,
  message = FALSE,
  warning = FALSE,
  fig.align = "center"
)

# Set theme
theme_set(theme_minimal(base_size = 12))
"""
        return self.add_chunk(code, name="setup", echo=False, message=False, warning=False)

    def add_deseq2_setup(self) -> "RMarkdownGenerator":
        """Add DESeq2 specific setup."""
        code = """# DESeq2 and related packages
library(DESeq2)
library(EnhancedVolcano)
library(pheatmap)
library(RColorBrewer)
library(ggrepel)
"""
        return self.add_chunk(code, name="deseq2-setup", message=False)

    def add_data_loading(
        self,
        path: str,
        variable: str = "data",
        file_type: str = "auto",
    ) -> "RMarkdownGenerator":
        """Add data loading chunk."""
        self.add_markdown(f"## Data Loading\n\nLoading data from `{path}`")

        if file_type == "auto":
            ext = Path(path).suffix.lower()
            file_type = {".csv": "csv", ".tsv": "tsv", ".rds": "rds"}.get(ext, "csv")

        if file_type == "csv":
            code = f'{variable} <- read_csv("{path}")'
        elif file_type == "tsv":
            code = f'{variable} <- read_tsv("{path}")'
        elif file_type == "rds":
            code = f'{variable} <- readRDS("{path}")'
        else:
            code = f'{variable} <- read_csv("{path}")'

        code += f"""

# Preview data
glimpse({variable})
DT::datatable(head({variable}, 100), options = list(scrollX = TRUE))
"""
        return self.add_chunk(code, name="data-loading")

    def add_section(self, title: str, level: int = 2) -> "RMarkdownGenerator":
        """Add section header."""
        header = "#" * level
        return self.add_markdown(f"\n{header} {title}\n")

    def add_volcano_plot(
        self,
        data_var: str = "results",
        fc_col: str = "log2FoldChange",
        pval_col: str = "padj",
        gene_col: str = "gene",
        fc_cutoff: float = 1.0,
        pval_cutoff: float = 0.05,
    ) -> "RMarkdownGenerator":
        """Add volcano plot with EnhancedVolcano."""
        self.add_section("Volcano Plot", level=3)

        code = f"""# Volcano Plot
EnhancedVolcano({data_var},
    lab = {data_var}${gene_col},
    x = '{fc_col}',
    y = '{pval_col}',
    pCutoff = {pval_cutoff},
    FCcutoff = {fc_cutoff},
    pointSize = 2.0,
    labSize = 3.0,
    title = 'Differential Expression',
    subtitle = 'Volcano Plot',
    legendPosition = 'right'
)
"""
        return self.add_chunk(code, name="volcano-plot", fig_width=10, fig_height=8)

    def add_heatmap(
        self,
        data_var: str = "expression_matrix",
        annotation_col: str | None = None,
        cluster_rows: bool = True,
        cluster_cols: bool = True,
    ) -> "RMarkdownGenerator":
        """Add heatmap with pheatmap."""
        self.add_section("Heatmap", level=3)

        annotation_line = ""
        if annotation_col:
            annotation_line = f"  annotation_col = {annotation_col},"

        code = f"""# Heatmap
pheatmap({data_var},
{annotation_line}
  cluster_rows = {str(cluster_rows).upper()},
  cluster_cols = {str(cluster_cols).upper()},
  scale = "row",
  color = colorRampPalette(rev(brewer.pal(n = 7, name = "RdBu")))(100),
  show_rownames = nrow({data_var}) <= 50,
  fontsize = 8,
  main = "Expression Heatmap"
)
"""
        return self.add_chunk(code, name="heatmap", fig_width=10, fig_height=10)

    def add_pca_plot(
        self,
        dds_var: str = "dds",
        intgroup: str = "condition",
    ) -> "RMarkdownGenerator":
        """Add PCA plot."""
        self.add_section("PCA Plot", level=3)

        code = f"""# PCA Plot
vsd <- vst({dds_var}, blind = FALSE)
pcaData <- plotPCA(vsd, intgroup = "{intgroup}", returnData = TRUE)
percentVar <- round(100 * attr(pcaData, "percentVar"))

ggplot(pcaData, aes(PC1, PC2, color = {intgroup})) +
  geom_point(size = 3) +
  xlab(paste0("PC1: ", percentVar[1], "% variance")) +
  ylab(paste0("PC2: ", percentVar[2], "% variance")) +
  ggtitle("PCA Plot") +
  theme_minimal()
"""
        return self.add_chunk(code, name="pca-plot", fig_width=8, fig_height=6)

    def add_ma_plot(
        self,
        results_var: str = "res",
    ) -> "RMarkdownGenerator":
        """Add MA plot."""
        self.add_section("MA Plot", level=3)

        code = f"""# MA Plot
plotMA({results_var}, ylim = c(-5, 5), main = "MA Plot")
"""
        return self.add_chunk(code, name="ma-plot", fig_width=8, fig_height=6)

    def add_summary_table(
        self,
        data_var: str = "results",
        n_top: int = 20,
    ) -> "RMarkdownGenerator":
        """Add summary table."""
        self.add_section("Top Differentially Expressed Genes", level=3)

        code = f"""# Top genes
top_genes <- {data_var} %>%
  filter(!is.na(padj)) %>%
  arrange(padj) %>%
  head({n_top})

DT::datatable(
  top_genes,
  options = list(scrollX = TRUE, pageLength = 10),
  caption = "Top {n_top} Differentially Expressed Genes"
)
"""
        return self.add_chunk(code, name="summary-table")

    def add_enrichment_plot(
        self,
        data_var: str = "enrichment",
        n_terms: int = 15,
    ) -> "RMarkdownGenerator":
        """Add enrichment bar plot."""
        self.add_section("Enrichment Results", level=3)

        code = f"""# Enrichment plot
top_terms <- {data_var} %>%
  slice_min(p.adjust, n = {n_terms})

ggplot(top_terms, aes(x = reorder(Description, -log10(p.adjust)), y = -log10(p.adjust))) +
  geom_bar(stat = "identity", fill = "steelblue") +
  coord_flip() +
  labs(x = "", y = "-log10(adjusted p-value)", title = "Top Enriched Terms") +
  theme_minimal()
"""
        return self.add_chunk(code, name="enrichment-plot", fig_width=10, fig_height=8)

    def add_session_info(self) -> "RMarkdownGenerator":
        """Add session info for reproducibility."""
        self.add_section("Session Information", level=2)
        code = "sessionInfo()"
        return self.add_chunk(code, name="session-info")

    def to_string(self) -> str:
        """Convert to R Markdown string."""
        return "\n".join(self.content)

    def save(self, path: str) -> str:
        """
        Save R Markdown document to file.

        Args:
            path: Output file path

        Returns:
            Absolute path to saved file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.suffix:
            path = path.with_suffix(".Rmd")

        path.write_text(self.to_string(), encoding="utf-8")
        return str(path.absolute())


def create_rmarkdown_report(
    title: str,
    report_type: str,
    data_path: str | None = None,
    output_path: str | None = None,
    **kwargs,
) -> str:
    """
    Create a pre-configured R Markdown report.

    Args:
        title: Report title
        report_type: Type of report (deseq2, enrichment, qc)
        data_path: Path to data file
        output_path: Output file path
        **kwargs: Additional parameters

    Returns:
        Path to saved report
    """
    rmd = RMarkdownGenerator(title=title)
    rmd.add_setup_chunk()

    if report_type == "deseq2":
        rmd.add_deseq2_setup()

        rmd.add_section("Introduction")
        rmd.add_markdown("""
This report presents the results of differential expression analysis
using DESeq2. The analysis identifies genes that are significantly
up- or down-regulated between experimental conditions.
""")

        if data_path:
            rmd.add_data_loading(data_path, "results")

        rmd.add_section("Quality Control")
        rmd.add_pca_plot()

        rmd.add_section("Differential Expression Results")
        rmd.add_volcano_plot()
        rmd.add_ma_plot()
        rmd.add_summary_table()

    elif report_type == "enrichment":
        rmd.add_chunk("library(clusterProfiler)", name="enrichment-setup")

        rmd.add_section("Introduction")
        rmd.add_markdown("""
This report presents functional enrichment analysis results.
""")

        if data_path:
            rmd.add_data_loading(data_path, "enrichment")

        rmd.add_enrichment_plot()

    elif report_type == "qc":
        rmd.add_section("Quality Control Report")
        rmd.add_markdown("Add your QC analysis here.")

    else:
        rmd.add_section("Analysis")
        rmd.add_markdown("Add your analysis code here.")
        rmd.add_chunk("# Your code here", name="analysis")

    rmd.add_session_info()

    # Save
    if output_path is None:
        output_path = f"{title.lower().replace(' ', '_')}.Rmd"

    return rmd.save(output_path)
