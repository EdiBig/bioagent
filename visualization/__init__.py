"""
Visualization module for BioAgent.

Provides tools for creating interactive plots, publication-quality figures,
and data visualizations for bioinformatics analyses.
"""

from .interactive import InteractivePlotter, create_interactive_plot
from .publication import PublicationFigure, JournalStyle
from .themes import (
    NATURE_THEME,
    CELL_THEME,
    SCIENCE_THEME,
    get_journal_theme,
    apply_theme,
)
from .utils import (
    save_figure,
    export_to_html,
    figure_to_base64,
    get_color_palette,
)

__all__ = [
    # Interactive plotting
    "InteractivePlotter",
    "create_interactive_plot",
    # Publication figures
    "PublicationFigure",
    "JournalStyle",
    # Themes
    "NATURE_THEME",
    "CELL_THEME",
    "SCIENCE_THEME",
    "get_journal_theme",
    "apply_theme",
    # Utilities
    "save_figure",
    "export_to_html",
    "figure_to_base64",
    "get_color_palette",
]
