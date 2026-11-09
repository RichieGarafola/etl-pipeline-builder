"""
Chart builders for the Streamlit UI.
"""

from __future__ import annotations

import plotly.graph_objects as go

from src.pipeline import PipelineResult

RAW_COLOR     = "#2E5FA3"
DROPPED_COLOR = "#E74C3C"
KEPT_COLOR    = "#2ECC71"


def build_row_count_figure(result: PipelineResult, font: dict | None = None) -> go.Figure:
    """
    Bar chart of the row count after each executed step.

    Bars are positioned by execution index, not by step name: Plotly merges
    identical category labels into one slot and stacks their bars, so a
    pipeline that runs two steps with the same name (e.g. two NormalizeText
    steps) would otherwise show one bar with the summed count. The tick
    labels (and hover text) carry the 1-based step number so repeated names stay distinct.
    """
    steps     = result.step_log
    positions = list(range(len(steps) + 1))
    names     = ["Raw"] + [f"{i}. {r.name}" for i, r in enumerate(steps, start=1)]
    # Wrap words onto separate lines so labels stay horizontal and unclipped.
    ticktext  = [n.replace(" ", "<br>") for n in names]
    values    = [result.rows_extracted] + [r.rows_out for r in steps]
    dropped   = [0] + [r.rows_dropped for r in steps]
    colors    = [RAW_COLOR] + [
        DROPPED_COLOR if r.rows_dropped > 0 else KEPT_COLOR
        for r in steps
    ]

    fig = go.Figure(go.Bar(
        x=positions, y=values,
        marker_color=colors,
        text=values, textposition="outside",
        customdata=list(zip(names, dropped)),
        hovertemplate="%{customdata[0]}<br>Rows: %{y:,}"
                      "<br>Dropped: %{customdata[1]:,}<extra></extra>",
    ))
    fig.update_layout(
        title="Row Count After Each Step",
        plot_bgcolor="white", paper_bgcolor="white", font=font,
        margin=dict(t=48, b=40, l=40, r=20),
        xaxis=dict(
            showgrid=False,
            tickmode="array", tickvals=positions, ticktext=ticktext,
        ),
        yaxis=dict(showgrid=True, gridcolor="#EEEEEE"),
    )
    return fig
