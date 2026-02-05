"""
Publication-quality figure generation.

Provides templates and tools for creating figures suitable for
Nature, Cell, Science, and other high-impact journals.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class JournalStyle(Enum):
    """Supported journal styles."""
    NATURE = "nature"
    CELL = "cell"
    SCIENCE = "science"
    PNAS = "pnas"
    BIOINFORMATICS = "bioinformatics"


@dataclass
class FigurePanel:
    """Configuration for a figure panel."""

    label: str  # Panel label (A, B, C, etc.)
    title: str = ""
    width_ratio: float = 1.0
    height_ratio: float = 1.0


class PublicationFigure:
    """
    Create publication-quality figures with journal-specific styling.

    Supports common bioinformatics visualizations including:
    - Volcano plots
    - Heatmaps with clustering
    - PCA/UMAP plots
    - Pathway diagrams
    - Survival curves
    - MA plots
    """

    def __init__(
        self,
        style: JournalStyle | str = JournalStyle.NATURE,
        figsize: tuple[float, float] | None = None,
        dpi: int = 300,
    ):
        """
        Initialize the figure generator.

        Args:
            style: Journal style
            figsize: Figure size in inches (auto if None)
            dpi: Resolution for raster output
        """
        import matplotlib.pyplot as plt

        if isinstance(style, str):
            style = JournalStyle(style.lower())

        self.style = style
        self.dpi = dpi

        # Get theme
        from .themes import get_journal_theme, apply_theme
        self.theme = get_journal_theme(style.value)
        apply_theme(self.theme)

        # Set figure size
        if figsize is None:
            self.figsize = (self.theme.single_column_width, self.theme.single_column_width * 0.75)
        else:
            self.figsize = figsize

        self.fig = None
        self.axes = None

    def create_figure(
        self,
        n_panels: int = 1,
        layout: str = "horizontal",
        width_ratios: list[float] | None = None,
        height_ratios: list[float] | None = None,
        panel_labels: list[str] | None = None,
    ) -> tuple[Any, Any]:
        """
        Create a multi-panel figure.

        Args:
            n_panels: Number of panels
            layout: Layout type ("horizontal", "vertical", "grid")
            width_ratios: Relative widths of columns
            height_ratios: Relative heights of rows
            panel_labels: Labels for panels (A, B, C, etc.)

        Returns:
            Tuple of (figure, axes)
        """
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        if panel_labels is None:
            panel_labels = [chr(65 + i) for i in range(n_panels)]  # A, B, C, ...

        # Determine grid dimensions
        if layout == "horizontal":
            n_rows, n_cols = 1, n_panels
        elif layout == "vertical":
            n_rows, n_cols = n_panels, 1
        else:  # grid
            n_cols = int(np.ceil(np.sqrt(n_panels)))
            n_rows = int(np.ceil(n_panels / n_cols))

        # Calculate figure size
        if layout == "horizontal":
            figsize = (self.theme.double_column_width, self.figsize[1])
        elif layout == "vertical":
            figsize = (self.figsize[0], self.figsize[1] * n_panels)
        else:
            figsize = (self.theme.double_column_width, self.figsize[1] * n_rows)

        # Create figure
        self.fig = plt.figure(figsize=figsize, dpi=self.dpi)

        # Create grid
        gs = GridSpec(
            n_rows, n_cols,
            figure=self.fig,
            width_ratios=width_ratios,
            height_ratios=height_ratios,
            wspace=0.3,
            hspace=0.3,
        )

        # Create axes
        self.axes = []
        for i in range(n_panels):
            row = i // n_cols
            col = i % n_cols
            ax = self.fig.add_subplot(gs[row, col])
            self.axes.append(ax)

            # Add panel label
            ax.text(
                -0.15, 1.05, panel_labels[i],
                transform=ax.transAxes,
                fontsize=self.theme.title_size + 2,
                fontweight="bold",
                va="bottom",
            )

        return self.fig, self.axes

    def volcano_plot(
        self,
        ax,
        data: dict | Any,
        x_col: str = "log2FoldChange",
        y_col: str = "pvalue",
        label_col: str | None = "gene",
        fc_threshold: float = 1.0,
        pval_threshold: float = 0.05,
        highlight_genes: list[str] | None = None,
        n_top_labels: int = 10,
        title: str = "",
    ):
        """
        Create a publication-quality volcano plot.

        Args:
            ax: Matplotlib axes
            data: DataFrame or dict with DE results
            x_col: Column for log2 fold change
            y_col: Column for p-value
            label_col: Column for gene labels
            fc_threshold: Fold change threshold
            pval_threshold: P-value threshold
            highlight_genes: Specific genes to highlight
            n_top_labels: Number of top genes to label
            title: Plot title
        """
        import pandas as pd

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Calculate -log10(p-value)
        df["neg_log10_pval"] = -np.log10(df[y_col].clip(lower=1e-300))

        # Classify significance
        up = (df[x_col] >= fc_threshold) & (df[y_col] <= pval_threshold)
        down = (df[x_col] <= -fc_threshold) & (df[y_col] <= pval_threshold)

        colors = self.theme.accent_colors

        # Plot non-significant
        ns = ~(up | down)
        ax.scatter(
            df.loc[ns, x_col],
            df.loc[ns, "neg_log10_pval"],
            c="#CCCCCC",
            s=self.theme.marker_size ** 2,
            alpha=0.5,
            linewidths=0,
            rasterized=True,
        )

        # Plot up-regulated
        ax.scatter(
            df.loc[up, x_col],
            df.loc[up, "neg_log10_pval"],
            c=colors[0],
            s=self.theme.marker_size ** 2,
            alpha=0.7,
            linewidths=0,
            label=f"Up ({up.sum()})",
            rasterized=True,
        )

        # Plot down-regulated
        ax.scatter(
            df.loc[down, x_col],
            df.loc[down, "neg_log10_pval"],
            c=colors[1],
            s=self.theme.marker_size ** 2,
            alpha=0.7,
            linewidths=0,
            label=f"Down ({down.sum()})",
            rasterized=True,
        )

        # Add threshold lines
        ax.axhline(-np.log10(pval_threshold), color="gray", linestyle="--", linewidth=0.5)
        ax.axvline(fc_threshold, color="gray", linestyle="--", linewidth=0.5)
        ax.axvline(-fc_threshold, color="gray", linestyle="--", linewidth=0.5)

        # Label top genes
        if label_col:
            sig_df = df[up | down].copy()
            sig_df["score"] = sig_df["neg_log10_pval"] * np.abs(sig_df[x_col])
            top_genes = sig_df.nlargest(n_top_labels, "score")

            if highlight_genes:
                highlight_df = df[df[label_col].isin(highlight_genes)]
                top_genes = pd.concat([top_genes, highlight_df]).drop_duplicates()

            for _, row in top_genes.iterrows():
                ax.annotate(
                    row[label_col],
                    (row[x_col], row["neg_log10_pval"]),
                    fontsize=self.theme.tick_size,
                    ha="center",
                    va="bottom",
                )

        ax.set_xlabel("log₂(Fold Change)")
        ax.set_ylabel("-log₁₀(p-value)")
        ax.legend(loc="upper right", frameon=False)

        if title:
            ax.set_title(title)

    def heatmap(
        self,
        ax,
        data: dict | Any,
        row_labels: list[str] | None = None,
        col_labels: list[str] | None = None,
        cmap: str = "RdBu_r",
        center: float | None = 0,
        vmin: float | None = None,
        vmax: float | None = None,
        cluster_rows: bool = True,
        cluster_cols: bool = True,
        show_colorbar: bool = True,
        row_colors: dict | None = None,
        col_colors: dict | None = None,
        title: str = "",
    ):
        """
        Create a publication-quality heatmap.

        Args:
            ax: Matplotlib axes
            data: 2D array or DataFrame
            row_labels: Row labels
            col_labels: Column labels
            cmap: Colormap
            center: Center value for diverging colormap
            vmin: Minimum value
            vmax: Maximum value
            cluster_rows: Cluster rows
            cluster_cols: Cluster columns
            show_colorbar: Show colorbar
            row_colors: Dict mapping row names to colors
            col_colors: Dict mapping column names to colors
            title: Plot title
        """
        import pandas as pd
        from scipy.cluster import hierarchy
        from scipy.spatial.distance import pdist

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        elif hasattr(data, "values"):
            df = data
        else:
            df = pd.DataFrame(data)

        values = df.values.astype(float)

        if row_labels is None:
            row_labels = list(df.index) if hasattr(df, "index") else list(range(values.shape[0]))
        if col_labels is None:
            col_labels = list(df.columns) if hasattr(df, "columns") else list(range(values.shape[1]))

        # Clustering
        row_order = list(range(values.shape[0]))
        col_order = list(range(values.shape[1]))

        if cluster_rows and values.shape[0] > 1:
            try:
                row_linkage = hierarchy.linkage(pdist(values), method="average")
                row_order = hierarchy.leaves_list(row_linkage)
            except Exception:
                pass

        if cluster_cols and values.shape[1] > 1:
            try:
                col_linkage = hierarchy.linkage(pdist(values.T), method="average")
                col_order = hierarchy.leaves_list(col_linkage)
            except Exception:
                pass

        # Reorder
        values = values[row_order, :][:, col_order]
        row_labels = [row_labels[i] for i in row_order]
        col_labels = [col_labels[i] for i in col_order]

        # Determine color limits
        if center is not None:
            max_abs = max(abs(values.min() - center), abs(values.max() - center))
            if vmin is None:
                vmin = center - max_abs
            if vmax is None:
                vmax = center + max_abs

        # Plot heatmap
        im = ax.imshow(
            values,
            aspect="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )

        # Set ticks
        ax.set_xticks(range(len(col_labels)))
        ax.set_yticks(range(len(row_labels)))
        ax.set_xticklabels(col_labels, rotation=45, ha="right")
        ax.set_yticklabels(row_labels)

        # Colorbar
        if show_colorbar:
            cbar = self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(labelsize=self.theme.tick_size)

        if title:
            ax.set_title(title)

    def pca_plot(
        self,
        ax,
        data: dict | Any,
        color_col: str | None = None,
        label_col: str | None = None,
        show_variance: bool = True,
        show_labels: bool = False,
        title: str = "",
    ):
        """
        Create a publication-quality PCA plot.

        Args:
            ax: Matplotlib axes
            data: DataFrame with PC1, PC2 or raw data
            color_col: Column for coloring
            label_col: Column for labels
            show_variance: Show variance explained
            show_labels: Show point labels
            title: Plot title
        """
        import pandas as pd
        from sklearn.decomposition import PCA

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Perform PCA if needed
        if "PC1" not in df.columns:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            pca = PCA(n_components=2)
            pcs = pca.fit_transform(df[numeric_cols])
            df["PC1"] = pcs[:, 0]
            df["PC2"] = pcs[:, 1]
            var_explained = pca.explained_variance_ratio_
        else:
            var_explained = [None, None]

        # Plot
        colors = self.theme.accent_colors

        if color_col and color_col in df.columns:
            groups = df[color_col].unique()
            for i, group in enumerate(groups):
                mask = df[color_col] == group
                ax.scatter(
                    df.loc[mask, "PC1"],
                    df.loc[mask, "PC2"],
                    c=colors[i % len(colors)],
                    s=self.theme.marker_size ** 2 * 4,
                    alpha=0.7,
                    label=group,
                    edgecolors="white",
                    linewidths=0.5,
                )
            ax.legend(loc="best", frameon=False)
        else:
            ax.scatter(
                df["PC1"],
                df["PC2"],
                c=colors[0],
                s=self.theme.marker_size ** 2 * 4,
                alpha=0.7,
                edgecolors="white",
                linewidths=0.5,
            )

        # Labels
        if show_labels and label_col:
            for _, row in df.iterrows():
                ax.annotate(
                    row[label_col],
                    (row["PC1"], row["PC2"]),
                    fontsize=self.theme.tick_size - 1,
                    alpha=0.7,
                )

        # Axis labels
        if show_variance and var_explained[0]:
            ax.set_xlabel(f"PC1 ({var_explained[0]*100:.1f}%)")
            ax.set_ylabel(f"PC2 ({var_explained[1]*100:.1f}%)")
        else:
            ax.set_xlabel("PC1")
            ax.set_ylabel("PC2")

        if title:
            ax.set_title(title)

    def ma_plot(
        self,
        ax,
        data: dict | Any,
        m_col: str = "log2FoldChange",
        a_col: str = "baseMean",
        pval_col: str = "padj",
        pval_threshold: float = 0.05,
        label_col: str | None = None,
        n_labels: int = 5,
        title: str = "",
    ):
        """
        Create a publication-quality MA plot.

        Args:
            ax: Matplotlib axes
            data: DataFrame with DE results
            m_col: Column for M values (log ratio)
            a_col: Column for A values (mean expression)
            pval_col: Column for p-values
            pval_threshold: Significance threshold
            label_col: Column for labels
            n_labels: Number of genes to label
            title: Plot title
        """
        import pandas as pd

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Calculate log10 mean
        df["log10_mean"] = np.log10(df[a_col].clip(lower=1))

        # Classify significance
        sig = df[pval_col] <= pval_threshold

        colors = self.theme.accent_colors

        # Plot non-significant
        ax.scatter(
            df.loc[~sig, "log10_mean"],
            df.loc[~sig, m_col],
            c="#CCCCCC",
            s=self.theme.marker_size ** 2,
            alpha=0.5,
            linewidths=0,
            rasterized=True,
        )

        # Plot significant
        ax.scatter(
            df.loc[sig, "log10_mean"],
            df.loc[sig, m_col],
            c=colors[0],
            s=self.theme.marker_size ** 2,
            alpha=0.7,
            linewidths=0,
            rasterized=True,
        )

        # Add horizontal line at 0
        ax.axhline(0, color="gray", linestyle="-", linewidth=0.5)

        # Label top genes
        if label_col and n_labels > 0:
            sig_df = df[sig].copy()
            sig_df["abs_m"] = np.abs(sig_df[m_col])
            top = sig_df.nlargest(n_labels, "abs_m")

            for _, row in top.iterrows():
                ax.annotate(
                    row[label_col],
                    (row["log10_mean"], row[m_col]),
                    fontsize=self.theme.tick_size,
                )

        ax.set_xlabel("log₁₀(Mean Expression)")
        ax.set_ylabel("log₂(Fold Change)")

        if title:
            ax.set_title(title)

    def enrichment_barplot(
        self,
        ax,
        data: dict | Any,
        term_col: str = "Term",
        pval_col: str = "P.value",
        count_col: str | None = "Count",
        n_terms: int = 10,
        title: str = "",
    ):
        """
        Create a publication-quality enrichment bar plot.

        Args:
            ax: Matplotlib axes
            data: DataFrame with enrichment results
            term_col: Column for term names
            pval_col: Column for p-values
            count_col: Column for gene counts
            n_terms: Number of terms to show
            title: Plot title
        """
        import pandas as pd

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Sort and take top n
        df = df.nsmallest(n_terms, pval_col).copy()
        df["neg_log10_pval"] = -np.log10(df[pval_col])

        colors = self.theme.accent_colors

        # Plot bars
        y_pos = range(len(df))
        bars = ax.barh(
            y_pos,
            df["neg_log10_pval"],
            color=colors[0],
            edgecolor="none",
        )

        # Customize
        ax.set_yticks(y_pos)
        ax.set_yticklabels(df[term_col])
        ax.set_xlabel("-log₁₀(p-value)")
        ax.invert_yaxis()

        # Add count labels if available
        if count_col and count_col in df.columns:
            for i, (bar, count) in enumerate(zip(bars, df[count_col])):
                ax.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"n={count}",
                    va="center",
                    fontsize=self.theme.tick_size,
                )

        if title:
            ax.set_title(title)

    def save(
        self,
        path: str,
        format: str | None = None,
        transparent: bool = False,
    ) -> str:
        """
        Save the figure.

        Args:
            path: Output path
            format: Output format (auto-detected if None)
            transparent: Transparent background

        Returns:
            Absolute path to saved file
        """
        if self.fig is None:
            raise ValueError("No figure to save. Create a figure first.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format is None:
            format = path.suffix.lstrip(".")

        self.fig.savefig(
            str(path),
            format=format,
            dpi=self.dpi,
            transparent=transparent,
            bbox_inches="tight",
            facecolor=self.fig.get_facecolor() if not transparent else "none",
        )

        return str(path.absolute())

    def close(self):
        """Close the figure to free memory."""
        import matplotlib.pyplot as plt
        if self.fig:
            plt.close(self.fig)
            self.fig = None
            self.axes = None
