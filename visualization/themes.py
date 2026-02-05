"""
Journal-specific visualization themes.

Provides publication-ready styling for Nature, Cell, Science, and other journals.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JournalTheme:
    """Theme configuration for journal-style figures."""

    # Basic properties
    name: str
    font_family: str = "Arial"
    font_size: int = 8
    title_size: int = 10
    label_size: int = 8
    tick_size: int = 7
    legend_size: int = 7

    # Figure dimensions (inches)
    single_column_width: float = 3.5  # ~89mm
    double_column_width: float = 7.0  # ~183mm
    max_height: float = 9.0

    # Colors
    primary_color: str = "#000000"
    accent_colors: list[str] = field(default_factory=lambda: [
        "#E64B35", "#4DBBD5", "#00A087", "#3C5488",
        "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"
    ])
    background_color: str = "#FFFFFF"
    grid_color: str = "#E0E0E0"

    # Line properties
    line_width: float = 0.75
    axis_line_width: float = 0.5
    border_width: float = 0.5

    # Markers
    marker_size: int = 4
    marker_edge_width: float = 0.5

    # DPI for export
    dpi: int = 300

    # Additional matplotlib rcParams
    rc_params: dict[str, Any] = field(default_factory=dict)

    def get_matplotlib_params(self) -> dict[str, Any]:
        """Return matplotlib rcParams for this theme."""
        params = {
            "font.family": self.font_family,
            "font.size": self.font_size,
            "axes.titlesize": self.title_size,
            "axes.labelsize": self.label_size,
            "xtick.labelsize": self.tick_size,
            "ytick.labelsize": self.tick_size,
            "legend.fontsize": self.legend_size,
            "axes.linewidth": self.axis_line_width,
            "lines.linewidth": self.line_width,
            "lines.markersize": self.marker_size,
            "patch.linewidth": self.border_width,
            "axes.edgecolor": self.primary_color,
            "axes.labelcolor": self.primary_color,
            "xtick.color": self.primary_color,
            "ytick.color": self.primary_color,
            "text.color": self.primary_color,
            "figure.facecolor": self.background_color,
            "axes.facecolor": self.background_color,
            "savefig.dpi": self.dpi,
            "savefig.facecolor": self.background_color,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "axes.grid": False,
        }
        params.update(self.rc_params)
        return params

    def get_plotly_template(self) -> dict[str, Any]:
        """Return Plotly template for this theme."""
        return {
            "layout": {
                "font": {
                    "family": self.font_family,
                    "size": self.font_size,
                    "color": self.primary_color,
                },
                "title": {"font": {"size": self.title_size}},
                "xaxis": {
                    "tickfont": {"size": self.tick_size},
                    "titlefont": {"size": self.label_size},
                    "linewidth": self.axis_line_width,
                    "showgrid": False,
                },
                "yaxis": {
                    "tickfont": {"size": self.tick_size},
                    "titlefont": {"size": self.label_size},
                    "linewidth": self.axis_line_width,
                    "showgrid": False,
                },
                "paper_bgcolor": self.background_color,
                "plot_bgcolor": self.background_color,
                "colorway": self.accent_colors,
                "legend": {"font": {"size": self.legend_size}},
            }
        }


# ── Pre-defined Journal Themes ──────────────────────────────────────────────

NATURE_THEME = JournalTheme(
    name="Nature",
    font_family="Arial",
    font_size=7,
    title_size=8,
    label_size=7,
    tick_size=6,
    legend_size=6,
    single_column_width=3.5,  # 89mm
    double_column_width=7.2,  # 183mm
    max_height=9.5,
    primary_color="#000000",
    accent_colors=[
        "#E64B35",  # Red
        "#4DBBD5",  # Cyan
        "#00A087",  # Teal
        "#3C5488",  # Blue
        "#F39B7F",  # Salmon
        "#8491B4",  # Gray-blue
        "#91D1C2",  # Light teal
        "#DC0000",  # Bright red
        "#7E6148",  # Brown
        "#B09C85",  # Tan
    ],
    line_width=0.75,
    axis_line_width=0.5,
    marker_size=3,
    dpi=300,
)

CELL_THEME = JournalTheme(
    name="Cell",
    font_family="Helvetica",
    font_size=7,
    title_size=9,
    label_size=7,
    tick_size=6,
    legend_size=6,
    single_column_width=3.42,  # 87mm
    double_column_width=7.0,   # 178mm
    max_height=9.0,
    primary_color="#000000",
    accent_colors=[
        "#1F77B4",  # Blue
        "#FF7F0E",  # Orange
        "#2CA02C",  # Green
        "#D62728",  # Red
        "#9467BD",  # Purple
        "#8C564B",  # Brown
        "#E377C2",  # Pink
        "#7F7F7F",  # Gray
        "#BCBD22",  # Olive
        "#17BECF",  # Cyan
    ],
    line_width=0.75,
    axis_line_width=0.5,
    marker_size=4,
    dpi=300,
)

SCIENCE_THEME = JournalTheme(
    name="Science",
    font_family="Helvetica",
    font_size=7,
    title_size=8,
    label_size=7,
    tick_size=6,
    legend_size=6,
    single_column_width=2.25,  # 57mm
    double_column_width=4.75,  # 121mm
    max_height=9.0,
    primary_color="#000000",
    accent_colors=[
        "#0072B2",  # Blue
        "#D55E00",  # Vermillion
        "#009E73",  # Green
        "#CC79A7",  # Pink
        "#F0E442",  # Yellow
        "#56B4E9",  # Sky blue
        "#E69F00",  # Orange
        "#000000",  # Black
    ],
    line_width=0.5,
    axis_line_width=0.5,
    marker_size=3,
    dpi=300,
)

PNAS_THEME = JournalTheme(
    name="PNAS",
    font_family="Helvetica",
    font_size=8,
    title_size=9,
    label_size=8,
    tick_size=7,
    legend_size=7,
    single_column_width=3.42,  # 8.7cm
    double_column_width=7.0,   # 17.8cm
    max_height=9.0,
    primary_color="#000000",
    accent_colors=[
        "#003f5c",
        "#2f4b7c",
        "#665191",
        "#a05195",
        "#d45087",
        "#f95d6a",
        "#ff7c43",
        "#ffa600",
    ],
    line_width=0.75,
    axis_line_width=0.5,
    marker_size=4,
    dpi=300,
)

BIOINFORMATICS_THEME = JournalTheme(
    name="Bioinformatics",
    font_family="Arial",
    font_size=8,
    title_size=9,
    label_size=8,
    tick_size=7,
    legend_size=7,
    single_column_width=3.35,  # 85mm
    double_column_width=6.85,  # 174mm
    max_height=9.0,
    primary_color="#000000",
    accent_colors=[
        "#377eb8",  # Blue
        "#e41a1c",  # Red
        "#4daf4a",  # Green
        "#984ea3",  # Purple
        "#ff7f00",  # Orange
        "#ffff33",  # Yellow
        "#a65628",  # Brown
        "#f781bf",  # Pink
    ],
    line_width=0.75,
    axis_line_width=0.5,
    marker_size=4,
    dpi=300,
)

# Theme registry
JOURNAL_THEMES = {
    "nature": NATURE_THEME,
    "cell": CELL_THEME,
    "science": SCIENCE_THEME,
    "pnas": PNAS_THEME,
    "bioinformatics": BIOINFORMATICS_THEME,
}


def get_journal_theme(journal: str) -> JournalTheme:
    """
    Get the theme for a specific journal.

    Args:
        journal: Journal name (nature, cell, science, pnas, bioinformatics)

    Returns:
        JournalTheme for the specified journal

    Raises:
        ValueError: If journal not found
    """
    journal_lower = journal.lower()
    if journal_lower not in JOURNAL_THEMES:
        available = ", ".join(JOURNAL_THEMES.keys())
        raise ValueError(f"Unknown journal: {journal}. Available: {available}")
    return JOURNAL_THEMES[journal_lower]


def apply_theme(theme: JournalTheme | str):
    """
    Apply a theme to matplotlib globally.

    Args:
        theme: JournalTheme object or journal name string
    """
    import matplotlib.pyplot as plt

    if isinstance(theme, str):
        theme = get_journal_theme(theme)

    plt.rcParams.update(theme.get_matplotlib_params())


def list_available_themes() -> list[str]:
    """Return list of available journal themes."""
    return list(JOURNAL_THEMES.keys())


# Color palettes for different data types
COLOR_PALETTES = {
    "categorical": [
        "#E64B35", "#4DBBD5", "#00A087", "#3C5488",
        "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"
    ],
    "sequential_blue": [
        "#f7fbff", "#deebf7", "#c6dbef", "#9ecae1",
        "#6baed6", "#4292c6", "#2171b5", "#084594"
    ],
    "sequential_red": [
        "#fff5f0", "#fee0d2", "#fcbba1", "#fc9272",
        "#fb6a4a", "#ef3b2c", "#cb181d", "#99000d"
    ],
    "diverging": [
        "#2166ac", "#4393c3", "#92c5de", "#d1e5f0",
        "#f7f7f7", "#fddbc7", "#f4a582", "#d6604d", "#b2182b"
    ],
    "heatmap": [
        "#313695", "#4575b4", "#74add1", "#abd9e9",
        "#e0f3f8", "#ffffbf", "#fee090", "#fdae61",
        "#f46d43", "#d73027", "#a50026"
    ],
    "expression": [
        "#0571b0", "#92c5de", "#f7f7f7", "#f4a582", "#ca0020"
    ],
}


def get_color_palette(name: str, n_colors: int | None = None) -> list[str]:
    """
    Get a color palette by name.

    Args:
        name: Palette name (categorical, sequential_blue, diverging, etc.)
        n_colors: Number of colors to return (default: all)

    Returns:
        List of hex color codes
    """
    if name not in COLOR_PALETTES:
        available = ", ".join(COLOR_PALETTES.keys())
        raise ValueError(f"Unknown palette: {name}. Available: {available}")

    palette = COLOR_PALETTES[name]
    if n_colors is not None:
        # Interpolate if needed
        if n_colors <= len(palette):
            # Sample evenly
            step = len(palette) / n_colors
            indices = [int(i * step) for i in range(n_colors)]
            return [palette[i] for i in indices]
        else:
            # Return all we have
            return palette

    return palette.copy()
