"""
Reporting module for BioAgent.

Provides tools for generating automated reports including:
- Jupyter notebooks
- R Markdown documents
- Interactive dashboards (Streamlit/Dash)
"""

from .notebook import NotebookGenerator, create_analysis_notebook
from .rmarkdown import RMarkdownGenerator, create_rmarkdown_report
from .dashboard import DashboardGenerator, create_dashboard

__all__ = [
    # Notebook generation
    "NotebookGenerator",
    "create_analysis_notebook",
    # R Markdown
    "RMarkdownGenerator",
    "create_rmarkdown_report",
    # Dashboard
    "DashboardGenerator",
    "create_dashboard",
]
