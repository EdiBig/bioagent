"""
Interactive plotting with Plotly and Bokeh.

Provides tools for creating zoomable, interactive figures for data exploration.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json


@dataclass
class PlotConfig:
    """Configuration for interactive plots."""

    width: int = 800
    height: int = 600
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    color_label: str = ""
    show_legend: bool = True
    template: str = "plotly_white"


class InteractivePlotter:
    """
    Create interactive plots using Plotly or Bokeh.

    Supports common bioinformatics visualizations with hover info,
    zoom, pan, and export capabilities.
    """

    def __init__(self, backend: str = "plotly"):
        """
        Initialize the plotter.

        Args:
            backend: Plotting backend ("plotly" or "bokeh")
        """
        self.backend = backend.lower()
        if self.backend not in ("plotly", "bokeh"):
            raise ValueError(f"Unsupported backend: {backend}")

    def volcano_plot(
        self,
        data: dict | Any,
        x_col: str = "log2FoldChange",
        y_col: str = "pvalue",
        label_col: str | None = "gene",
        color_col: str | None = None,
        fc_threshold: float = 1.0,
        pval_threshold: float = 0.05,
        title: str = "Volcano Plot",
        width: int = 800,
        height: int = 600,
        highlight_genes: list[str] | None = None,
    ) -> Any:
        """
        Create an interactive volcano plot.

        Args:
            data: DataFrame or dict with columns
            x_col: Column for log2 fold change
            y_col: Column for p-value
            label_col: Column for point labels
            color_col: Column for point colors
            fc_threshold: Fold change threshold for significance
            pval_threshold: P-value threshold for significance
            title: Plot title
            width: Plot width
            height: Plot height
            highlight_genes: Genes to highlight with labels

        Returns:
            Plotly or Bokeh figure
        """
        import pandas as pd
        import numpy as np

        # Convert to DataFrame if needed
        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Calculate -log10(p-value)
        df["neg_log10_pval"] = -np.log10(df[y_col].clip(lower=1e-300))

        # Classify points
        if color_col is None:
            conditions = [
                (df[x_col] >= fc_threshold) & (df[y_col] <= pval_threshold),
                (df[x_col] <= -fc_threshold) & (df[y_col] <= pval_threshold),
            ]
            choices = ["Up", "Down"]
            df["significance"] = np.select(conditions, choices, default="NS")
            color_col = "significance"

        if self.backend == "plotly":
            return self._volcano_plotly(
                df, x_col, "neg_log10_pval", label_col, color_col,
                fc_threshold, pval_threshold, title, width, height, highlight_genes
            )
        else:
            return self._volcano_bokeh(
                df, x_col, "neg_log10_pval", label_col, color_col,
                fc_threshold, pval_threshold, title, width, height, highlight_genes
            )

    def _volcano_plotly(
        self, df, x_col, y_col, label_col, color_col,
        fc_threshold, pval_threshold, title, width, height, highlight_genes
    ):
        """Create volcano plot with Plotly."""
        import numpy as np
        import plotly.express as px
        import plotly.graph_objects as go

        color_map = {"Up": "#E64B35", "Down": "#4DBBD5", "NS": "#CCCCCC"}

        fig = px.scatter(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            hover_name=label_col,
            color_discrete_map=color_map,
            title=title,
            width=width,
            height=height,
        )

        # Add threshold lines
        fig.add_hline(
            y=-np.log10(pval_threshold),
            line_dash="dash",
            line_color="gray",
            annotation_text=f"p={pval_threshold}",
        )
        fig.add_vline(x=fc_threshold, line_dash="dash", line_color="gray")
        fig.add_vline(x=-fc_threshold, line_dash="dash", line_color="gray")

        # Add labels for highlighted genes
        if highlight_genes and label_col:
            highlight_df = df[df[label_col].isin(highlight_genes)]
            for _, row in highlight_df.iterrows():
                fig.add_annotation(
                    x=row[x_col],
                    y=row[y_col],
                    text=row[label_col],
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    ax=20,
                    ay=-20,
                )

        fig.update_layout(
            xaxis_title="log₂(Fold Change)",
            yaxis_title="-log₁₀(p-value)",
            legend_title="",
        )

        return fig

    def _volcano_bokeh(
        self, df, x_col, y_col, label_col, color_col,
        fc_threshold, pval_threshold, title, width, height, highlight_genes
    ):
        """Create volcano plot with Bokeh."""
        from bokeh.plotting import figure
        from bokeh.models import ColumnDataSource, HoverTool, Span
        import numpy as np

        color_map = {"Up": "#E64B35", "Down": "#4DBBD5", "NS": "#CCCCCC"}
        df["color"] = df[color_col].map(color_map)

        source = ColumnDataSource(df)

        p = figure(
            title=title,
            width=width,
            height=height,
            x_axis_label="log₂(Fold Change)",
            y_axis_label="-log₁₀(p-value)",
            tools="pan,wheel_zoom,box_zoom,reset,save",
        )

        p.scatter(
            x_col, y_col,
            source=source,
            color="color",
            size=8,
            alpha=0.6,
        )

        # Add hover tool
        hover = HoverTool(
            tooltips=[
                ("Gene", f"@{label_col}") if label_col else ("Index", "$index"),
                ("log2FC", f"@{x_col}{{0.2f}}"),
                ("-log10(p)", f"@{y_col}{{0.2f}}"),
            ]
        )
        p.add_tools(hover)

        # Add threshold lines
        p.add_layout(Span(location=-np.log10(pval_threshold), dimension="width", line_dash="dashed"))
        p.add_layout(Span(location=fc_threshold, dimension="height", line_dash="dashed"))
        p.add_layout(Span(location=-fc_threshold, dimension="height", line_dash="dashed"))

        return p

    def scatter_plot(
        self,
        data: dict | Any,
        x_col: str,
        y_col: str,
        color_col: str | None = None,
        size_col: str | None = None,
        label_col: str | None = None,
        title: str = "Scatter Plot",
        width: int = 800,
        height: int = 600,
        trendline: bool = False,
    ) -> Any:
        """
        Create an interactive scatter plot.

        Args:
            data: DataFrame or dict
            x_col: X-axis column
            y_col: Y-axis column
            color_col: Color column
            size_col: Size column
            label_col: Label column for hover
            title: Plot title
            width: Plot width
            height: Plot height
            trendline: Add trendline

        Returns:
            Interactive figure
        """
        import pandas as pd

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data

        if self.backend == "plotly":
            import plotly.express as px

            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                size=size_col,
                hover_name=label_col,
                title=title,
                width=width,
                height=height,
                trendline="ols" if trendline else None,
            )
            return fig

        else:
            from bokeh.plotting import figure
            from bokeh.models import ColumnDataSource, HoverTool

            source = ColumnDataSource(df)

            p = figure(
                title=title,
                width=width,
                height=height,
                x_axis_label=x_col,
                y_axis_label=y_col,
                tools="pan,wheel_zoom,box_zoom,reset,save",
            )

            p.scatter(x_col, y_col, source=source, size=8, alpha=0.6)

            hover = HoverTool(tooltips=[
                (x_col, f"@{x_col}"),
                (y_col, f"@{y_col}"),
            ])
            p.add_tools(hover)

            return p

    def heatmap(
        self,
        data: dict | Any,
        x_labels: list[str] | None = None,
        y_labels: list[str] | None = None,
        title: str = "Heatmap",
        colorscale: str = "RdBu_r",
        width: int = 800,
        height: int = 600,
        cluster_rows: bool = False,
        cluster_cols: bool = False,
    ) -> Any:
        """
        Create an interactive heatmap.

        Args:
            data: 2D array or DataFrame
            x_labels: Column labels
            y_labels: Row labels
            title: Plot title
            colorscale: Color scale name
            width: Plot width
            height: Plot height
            cluster_rows: Cluster rows
            cluster_cols: Cluster columns

        Returns:
            Interactive figure
        """
        import pandas as pd
        import numpy as np

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        elif hasattr(data, "values"):
            df = data
        else:
            df = pd.DataFrame(data)

        values = df.values

        if x_labels is None:
            x_labels = list(df.columns) if hasattr(df, "columns") else list(range(values.shape[1]))
        if y_labels is None:
            y_labels = list(df.index) if hasattr(df, "index") else list(range(values.shape[0]))

        # Clustering
        if cluster_rows or cluster_cols:
            try:
                from scipy.cluster import hierarchy
                from scipy.spatial.distance import pdist

                if cluster_rows:
                    row_linkage = hierarchy.linkage(pdist(values), method="average")
                    row_order = hierarchy.leaves_list(row_linkage)
                    values = values[row_order, :]
                    y_labels = [y_labels[i] for i in row_order]

                if cluster_cols:
                    col_linkage = hierarchy.linkage(pdist(values.T), method="average")
                    col_order = hierarchy.leaves_list(col_linkage)
                    values = values[:, col_order]
                    x_labels = [x_labels[i] for i in col_order]
            except ImportError:
                pass

        if self.backend == "plotly":
            import plotly.graph_objects as go

            fig = go.Figure(data=go.Heatmap(
                z=values,
                x=x_labels,
                y=y_labels,
                colorscale=colorscale,
                hoverongaps=False,
            ))

            fig.update_layout(
                title=title,
                width=width,
                height=height,
            )

            return fig

        else:
            from bokeh.plotting import figure
            from bokeh.models import LinearColorMapper, ColorBar
            from bokeh.palettes import RdBu11

            p = figure(
                title=title,
                width=width,
                height=height,
                x_range=x_labels,
                y_range=y_labels,
                tools="hover,save",
            )

            mapper = LinearColorMapper(
                palette=RdBu11,
                low=values.min(),
                high=values.max(),
            )

            # Create rectangles for each cell
            xs, ys, vals = [], [], []
            for i, y in enumerate(y_labels):
                for j, x in enumerate(x_labels):
                    xs.append(x)
                    ys.append(y)
                    vals.append(values[i, j])

            p.rect(
                x=xs, y=ys, width=1, height=1,
                fill_color={"field": "value", "transform": mapper},
                source={"x": xs, "y": ys, "value": vals},
            )

            color_bar = ColorBar(color_mapper=mapper, location=(0, 0))
            p.add_layout(color_bar, "right")

            return p

    def pca_plot(
        self,
        data: dict | Any,
        color_col: str | None = None,
        label_col: str | None = None,
        title: str = "PCA Plot",
        width: int = 800,
        height: int = 600,
        show_loadings: bool = False,
    ) -> Any:
        """
        Create an interactive PCA plot.

        Args:
            data: DataFrame with PC1, PC2 columns or raw data for PCA
            color_col: Column for coloring points
            label_col: Column for labels
            title: Plot title
            width: Plot width
            height: Plot height
            show_loadings: Show feature loadings

        Returns:
            Interactive figure
        """
        import pandas as pd
        import numpy as np

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        # Check if PCA already done
        if "PC1" not in df.columns:
            # Perform PCA
            from sklearn.decomposition import PCA

            numeric_cols = df.select_dtypes(include=[np.number]).columns
            pca = PCA(n_components=2)
            pcs = pca.fit_transform(df[numeric_cols])
            df["PC1"] = pcs[:, 0]
            df["PC2"] = pcs[:, 1]
            variance_explained = pca.explained_variance_ratio_
        else:
            variance_explained = [None, None]

        x_label = f"PC1 ({variance_explained[0]*100:.1f}%)" if variance_explained[0] else "PC1"
        y_label = f"PC2 ({variance_explained[1]*100:.1f}%)" if variance_explained[1] else "PC2"

        if self.backend == "plotly":
            import plotly.express as px

            fig = px.scatter(
                df,
                x="PC1",
                y="PC2",
                color=color_col,
                hover_name=label_col,
                title=title,
                width=width,
                height=height,
            )

            fig.update_layout(
                xaxis_title=x_label,
                yaxis_title=y_label,
            )

            return fig

        else:
            from bokeh.plotting import figure
            from bokeh.models import ColumnDataSource, HoverTool

            source = ColumnDataSource(df)

            p = figure(
                title=title,
                width=width,
                height=height,
                x_axis_label=x_label,
                y_axis_label=y_label,
                tools="pan,wheel_zoom,box_zoom,reset,save",
            )

            p.scatter("PC1", "PC2", source=source, size=10, alpha=0.7)

            if label_col:
                hover = HoverTool(tooltips=[(label_col, f"@{label_col}")])
                p.add_tools(hover)

            return p

    def bar_plot(
        self,
        data: dict | Any,
        x_col: str,
        y_col: str,
        color_col: str | None = None,
        title: str = "Bar Plot",
        width: int = 800,
        height: int = 600,
        orientation: str = "v",
    ) -> Any:
        """
        Create an interactive bar plot.

        Args:
            data: DataFrame or dict
            x_col: X-axis column
            y_col: Y-axis column
            color_col: Color column
            title: Plot title
            width: Plot width
            height: Plot height
            orientation: "v" for vertical, "h" for horizontal

        Returns:
            Interactive figure
        """
        import pandas as pd

        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data

        if self.backend == "plotly":
            import plotly.express as px

            fig = px.bar(
                df,
                x=x_col if orientation == "v" else y_col,
                y=y_col if orientation == "v" else x_col,
                color=color_col,
                title=title,
                width=width,
                height=height,
                orientation=orientation,
            )

            return fig

        else:
            from bokeh.plotting import figure
            from bokeh.models import ColumnDataSource

            source = ColumnDataSource(df)

            p = figure(
                title=title,
                width=width,
                height=height,
                x_range=df[x_col].tolist() if orientation == "v" else None,
                y_range=df[x_col].tolist() if orientation == "h" else None,
                tools="save",
            )

            if orientation == "v":
                p.vbar(x=x_col, top=y_col, source=source, width=0.7)
            else:
                p.hbar(y=x_col, right=y_col, source=source, height=0.7)

            return p

    def save(self, fig, path: str, **kwargs) -> str:
        """Save figure to file."""
        from .utils import save_figure
        return save_figure(fig, path, **kwargs)


def create_interactive_plot(
    plot_type: str,
    data: dict | Any,
    backend: str = "plotly",
    **kwargs,
) -> Any:
    """
    Convenience function to create interactive plots.

    Args:
        plot_type: Type of plot (volcano, scatter, heatmap, pca, bar)
        data: Data for the plot
        backend: Plotting backend (plotly or bokeh)
        **kwargs: Additional arguments for the specific plot type

    Returns:
        Interactive figure
    """
    plotter = InteractivePlotter(backend=backend)

    plot_methods = {
        "volcano": plotter.volcano_plot,
        "scatter": plotter.scatter_plot,
        "heatmap": plotter.heatmap,
        "pca": plotter.pca_plot,
        "bar": plotter.bar_plot,
    }

    if plot_type not in plot_methods:
        available = ", ".join(plot_methods.keys())
        raise ValueError(f"Unknown plot type: {plot_type}. Available: {available}")

    return plot_methods[plot_type](data, **kwargs)
