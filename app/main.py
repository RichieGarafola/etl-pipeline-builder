"""
ETL Pipeline Builder — Configure and run a multi-step Extract → Transform → Load pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.extractor   import extract_csv, extract_sample
from src.pipeline    import run_pipeline, default_steps, PipelineResult
from src.loader      import load_csv, load_sqlite_sql, load_excel
from src.transformer import (
    NormalizeHeaders, StripStrings, DropDuplicates, DropNullRows,
    FillNulls, NormalizeText, CoerceNumeric, CoerceDates,
    FilterRows, RenameColumns, STEP_REGISTRY,
)

st.set_page_config(
    page_title="ETL Pipeline Builder",
    page_icon="⚙",
    layout="wide",
)

NAVY = "#1B2A4A"
BLUE = "#2E5FA3"
FONT = dict(family="Inter, Segoe UI, sans-serif", color="#333333")


# ── Sidebar: source ────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("ETL Pipeline Builder")
    st.markdown("---")
    st.subheader("1. Data Source")
    use_sample = st.toggle("Use sample data", value=True)
    uploaded = None
    if not use_sample:
        uploaded = st.file_uploader("Upload raw CSV", type=["csv"])

    st.markdown("---")
    st.subheader("2. Pipeline Steps")
    st.caption("Steps execute top-to-bottom in order.")

    use_default = st.toggle("Use default pipeline", value=True)


# ── Build step list ────────────────────────────────────────────────────────────
if use_default:
    steps = default_steps()
else:
    # Dynamic step builder
    selected_step_names = st.sidebar.multiselect(
        "Add steps (executed in order):",
        options=list(STEP_REGISTRY.keys()),
        default=["Normalize Headers", "Strip Whitespace", "Drop Duplicates"],
    )
    steps = []
    for name in selected_step_names:
        cls = STEP_REGISTRY[name]
        # Instantiate with defaults; advanced config available in expanders below
        steps.append(cls())


# ── Run pipeline ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Running pipeline...")
def cached_run(file_bytes: bytes | None) -> PipelineResult:
    import io
    src = io.BytesIO(file_bytes) if file_bytes else None
    return run_pipeline(default_steps() if use_default else steps, source_path=src)


if use_sample:
    result = cached_run(None)
elif uploaded:
    result = cached_run(uploaded.read())
else:
    st.info("Upload a CSV or enable sample data to get started.")
    st.stop()

if not result.success:
    st.error(f"Pipeline failed: {result.error}")
    st.stop()


# ── Header ─────────────────────────────────────────────────────────────────────
st.header("ETL Pipeline Builder")
st.caption(f"Source: `{result.source_path}`  |  {len(steps)} steps  |  "
           f"{result.total_duration_ms:.1f} ms total")

st.markdown("---")

# ── KPI tiles ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows Extracted",  f"{result.rows_extracted:,}")
c2.metric("Rows Loaded",     f"{result.rows_loaded:,}")
c3.metric("Rows Dropped",    f"{result.rows_dropped_total:,}",
          delta=f"-{result.rows_dropped_total}", delta_color="off")
c4.metric("Pipeline Steps",  f"{len(result.step_log)}")

st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Run Log", "Output Data", "Before vs After", "Download"])


# ── Tab 1: Run Log ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Pipeline Run Log")
    log_df = result.summary_df()

    def color_dropped(val):
        if isinstance(val, (int, float)) and val > 0:
            return "color: #E74C3C; font-weight: bold"
        return ""

    st.dataframe(
        log_df.style.map(color_dropped, subset=["Rows Dropped"]).format({
            "Rows In":       "{:,}",
            "Rows Out":      "{:,}",
            "Rows Dropped":  "{:,}",
            "Duration (ms)": "{:.1f}",
        }),
        use_container_width=True,
    )

    # Step-by-step row count funnel chart
    labels = ["Raw"] + [r.name for r in result.step_log]
    values = [result.rows_extracted] + [r.rows_out for r in result.step_log]
    colors = [BLUE] + [
        "#E74C3C" if r.rows_dropped > 0 else "#2ECC71"
        for r in result.step_log
    ]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=values, textposition="outside",
    ))
    fig.update_layout(
        title="Row Count After Each Step",
        plot_bgcolor="white", paper_bgcolor="white", font=FONT,
        margin=dict(t=48, b=40, l=40, r=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#EEEEEE"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tab 2: Output Data ─────────────────────────────────────────────────────────
with tab2:
    st.subheader(f"Transformed Data ({result.rows_loaded:,} rows × {len(result.output_df.columns)} cols)")
    st.dataframe(result.output_df, use_container_width=True, height=500)


# ── Tab 3: Before vs After ─────────────────────────────────────────────────────
with tab3:
    st.subheader("Raw vs. Transformed — Side by Side")
    try:
        raw = extract_sample() if use_sample else extract_csv(None)
    except Exception:
        raw = pd.DataFrame()

    col_l, col_r = st.columns(2)
    with col_l:
        st.caption(f"**Raw** ({len(raw):,} rows)")
        st.dataframe(raw.head(30), use_container_width=True, height=420)
    with col_r:
        st.caption(f"**Transformed** ({result.rows_loaded:,} rows)")
        st.dataframe(result.output_df.head(30), use_container_width=True, height=420)

    # Null count comparison
    if not raw.empty:
        null_raw   = raw.isnull().sum() + (raw == "").sum()
        null_clean = result.output_df.isnull().sum()
        null_df = pd.DataFrame({
            "Column":     null_raw.index,
            "Nulls (Raw)": null_raw.values,
        }).merge(
            pd.DataFrame({"Column": null_clean.index, "Nulls (Clean)": null_clean.values}),
            on="Column", how="outer",
        ).fillna(0).astype({"Nulls (Raw)": int, "Nulls (Clean)": int})
        null_df["Improvement"] = null_df["Nulls (Raw)"] - null_df["Nulls (Clean)"]
        st.markdown("**Null / Empty Count Change**")
        st.dataframe(null_df, use_container_width=True)


# ── Tab 4: Download ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Export Transformed Data")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("**CSV**")
        csv_buf = load_csv(result.output_df)
        st.download_button(
            "Download as CSV",
            data=csv_buf,
            file_name="etl_output.csv",
            mime="text/csv",
        )

    with col_b:
        st.markdown("**Excel**")
        xlsx_buf = load_excel(result.output_df)
        st.download_button(
            "Download as Excel",
            data=xlsx_buf,
            file_name="etl_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_c:
        st.markdown("**SQL Dump**")
        sql_buf = load_sqlite_sql(result.output_df, table="contracts")
        st.download_button(
            "Download as SQL (.sql)",
            data=sql_buf,
            file_name="etl_output.sql",
            mime="text/plain",
        )

    st.markdown("---")
    st.markdown("**Audit Log**")
    st.caption("Step-by-step row count and timing — matches the Run Log table.")
    audit_buf = load_csv(result.summary_df())
    st.download_button(
        "Download Audit Log",
        data=audit_buf,
        file_name="etl_audit_log.csv",
        mime="text/csv",
    )
