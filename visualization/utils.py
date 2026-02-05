"""
Visualization utility functions.

Provides helper functions for saving, exporting, and manipulating figures.
"""

import base64
import io
import json
from pathlib import Path
from typing import Any


def save_figure(
    fig,
    path: str,
    format: str | None = None,
    dpi: int = 300,
    transparent: bool = False,
    **kwargs,
) -> str:
    """
    Save a figure to file with automatic format detection.

    Args:
        fig: Matplotlib figure, Plotly figure, or Bokeh figure
        path: Output file path
        format: Output format (auto-detected from extension if None)
        dpi: Resolution for raster formats
        transparent: Whether to use transparent background
        **kwargs: Additional arguments passed to save function

    Returns:
        Absolute path to saved file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format is None:
        format = path.suffix.lstrip(".").lower()

    # Detect figure type and save accordingly
    fig_type = type(fig).__module__

    if "matplotlib" in fig_type or hasattr(fig, "savefig"):
        # Matplotlib figure
        fig.savefig(
            str(path),
            format=format,
            dpi=dpi,
            transparent=transparent,
            bbox_inches="tight",
            **kwargs,
        )

    elif "plotly" in fig_type:
        # Plotly figure
        if format in ("html", "htm"):
            fig.write_html(str(path), **kwargs)
        elif format == "json":
            fig.write_json(str(path), **kwargs)
        else:
            fig.write_image(str(path), scale=dpi / 72, **kwargs)

    elif "bokeh" in fig_type:
        # Bokeh figure
        from bokeh.io import export_png, export_svgs
        from bokeh.io.export import get_screenshot_as_png

        if format == "html":
            from bokeh.embed import file_html
            from bokeh.resources import CDN

            html = file_html(fig, CDN, "figure")
            path.write_text(html)
        elif format == "png":
            export_png(fig, filename=str(path))
        elif format == "svg":
            fig.output_backend = "svg"
            export_svgs(fig, filename=str(path))
        else:
            # Default to PNG
            export_png(fig, filename=str(path))

    else:
        raise TypeError(f"Unsupported figure type: {type(fig)}")

    return str(path.absolute())


def export_to_html(
    fig,
    path: str | None = None,
    include_plotlyjs: bool = True,
    full_html: bool = True,
) -> str:
    """
    Export a figure to interactive HTML.

    Args:
        fig: Plotly or Bokeh figure
        path: Output path (if None, returns HTML string)
        include_plotlyjs: Whether to include Plotly.js library
        full_html: Whether to include full HTML document structure

    Returns:
        Path to saved file or HTML string
    """
    fig_type = type(fig).__module__

    if "plotly" in fig_type:
        if path:
            fig.write_html(
                path,
                include_plotlyjs=include_plotlyjs,
                full_html=full_html,
            )
            return path
        else:
            return fig.to_html(
                include_plotlyjs=include_plotlyjs,
                full_html=full_html,
            )

    elif "bokeh" in fig_type:
        from bokeh.embed import file_html, components
        from bokeh.resources import CDN

        if full_html:
            html = file_html(fig, CDN, "figure")
        else:
            script, div = components(fig)
            html = f"{script}\n{div}"

        if path:
            Path(path).write_text(html)
            return path
        else:
            return html

    else:
        raise TypeError(f"Unsupported figure type for HTML export: {type(fig)}")


def figure_to_base64(
    fig,
    format: str = "png",
    dpi: int = 150,
) -> str:
    """
    Convert a figure to base64-encoded string.

    Useful for embedding in HTML or notebooks.

    Args:
        fig: Matplotlib or Plotly figure
        format: Image format (png, svg, jpg)
        dpi: Resolution for raster formats

    Returns:
        Base64-encoded string
    """
    fig_type = type(fig).__module__

    if "matplotlib" in fig_type or hasattr(fig, "savefig"):
        buf = io.BytesIO()
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches="tight")
        buf.seek(0)
        data = base64.b64encode(buf.read()).decode("utf-8")

    elif "plotly" in fig_type:
        img_bytes = fig.to_image(format=format, scale=dpi / 72)
        data = base64.b64encode(img_bytes).decode("utf-8")

    else:
        raise TypeError(f"Unsupported figure type: {type(fig)}")

    return data


def get_color_palette(
    palette: str = "categorical",
    n_colors: int | None = None,
) -> list[str]:
    """
    Get a color palette for plotting.

    Args:
        palette: Palette name or type
        n_colors: Number of colors needed

    Returns:
        List of hex color codes
    """
    from .themes import COLOR_PALETTES

    if palette in COLOR_PALETTES:
        colors = COLOR_PALETTES[palette]
    else:
        # Default categorical
        colors = COLOR_PALETTES["categorical"]

    if n_colors and n_colors <= len(colors):
        return colors[:n_colors]

    return colors


def create_subplot_grid(
    n_plots: int,
    max_cols: int = 3,
    figsize_per_plot: tuple[float, float] = (4, 3),
) -> tuple[Any, Any]:
    """
    Create a figure with subplot grid.

    Args:
        n_plots: Number of plots to create
        max_cols: Maximum columns
        figsize_per_plot: Size per subplot

    Returns:
        Tuple of (figure, axes array)
    """
    import matplotlib.pyplot as plt
    import numpy as np

    n_cols = min(n_plots, max_cols)
    n_rows = int(np.ceil(n_plots / n_cols))

    figsize = (figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)

    # Flatten axes array
    if n_plots == 1:
        axes = np.array([axes])
    else:
        axes = axes.flatten()

    # Hide unused axes
    for i in range(n_plots, len(axes)):
        axes[i].set_visible(False)

    return fig, axes[:n_plots]


def add_scalebar(
    ax,
    length: float,
    label: str = "",
    location: str = "lower right",
    color: str = "black",
    fontsize: int = 8,
):
    """
    Add a scale bar to an axes (useful for images).

    Args:
        ax: Matplotlib axes
        length: Scale bar length in data units
        label: Label text
        location: Position (lower right, lower left, etc.)
        color: Bar and text color
        fontsize: Label font size
    """
    from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar
    import matplotlib.font_manager as fm

    fontprops = fm.FontProperties(size=fontsize)
    scalebar = AnchoredSizeBar(
        ax.transData,
        length,
        label,
        location,
        pad=0.5,
        color=color,
        frameon=False,
        size_vertical=length / 20,
        fontproperties=fontprops,
    )
    ax.add_artist(scalebar)


def adjust_text_labels(ax, texts: list = None, **kwargs):
    """
    Adjust text labels to avoid overlap.

    Args:
        ax: Matplotlib axes
        texts: List of text objects (if None, uses all texts on axes)
        **kwargs: Arguments for adjustText.adjust_text
    """
    try:
        from adjustText import adjust_text

        if texts is None:
            texts = ax.texts

        adjust_text(texts, ax=ax, **kwargs)
    except ImportError:
        # adjustText not installed, skip
        pass


def format_pvalue(p: float, threshold: float = 0.001) -> str:
    """
    Format p-value for display.

    Args:
        p: P-value
        threshold: Threshold below which to use scientific notation

    Returns:
        Formatted string
    """
    if p < threshold:
        return f"p < {threshold}"
    elif p < 0.01:
        return f"p = {p:.3f}"
    elif p < 0.05:
        return f"p = {p:.2f}"
    else:
        return f"p = {p:.2f}"


def format_fold_change(fc: float) -> str:
    """
    Format fold change for display.

    Args:
        fc: Fold change (can be log2)

    Returns:
        Formatted string
    """
    if abs(fc) > 100:
        return f"{fc:.0f}"
    elif abs(fc) > 10:
        return f"{fc:.1f}"
    else:
        return f"{fc:.2f}"
