"""
app.py  –  MA DOR Tax Compliance Analytics  (landing page)
"""

import streamlit as st
import pandas as pd
import data_cleaner

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MA DOR Tax Compliance Analytics",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Sidebar accent */
    [data-testid="stSidebar"] { background-color: #f0f4f8; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 18px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #64748b; }
    [data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; color: #1e3a5f; }

    /* Page header */
    .page-title {
        font-size: 2rem;
        font-weight: 800;
        color: #1e3a5f;
        margin-bottom: 0;
    }
    .page-subtitle {
        font-size: 1rem;
        color: #64748b;
        margin-top: 0;
    }
    hr.divider { border: 1px solid #e2e8f0; margin: 1rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("## 🏛️")
with col_title:
    st.markdown('<p class="page-title">MA DOR Tax Compliance Analytics</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Massachusetts Department of Revenue · Internal Analysis Tool</p>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Upload section ─────────────────────────────────────────────────────────
st.subheader("Upload Taxpayer Dataset")
st.markdown(
    "Upload a **CSV or Excel** file exported from DOR systems. "
    "The tool will automatically clean, standardise, and load your data."
)

uploaded = st.file_uploader(
    label="Choose file",
    type=["csv", "xlsx", "xls"],
    help="Accepted formats: .csv, .xlsx, .xls",
)

use_sample = st.checkbox(
    "Use sample dataset",
    value=False,
    help="Load the built-in MA tax compliance sample data to explore the tool without uploading a file.",
)

# Determine source: uploaded file takes priority over sample dataset
data_source = uploaded if uploaded else (
    open("data/ma_tax_compliance_data.csv", "rb") if use_sample else None
)
source_label = "File loaded successfully" if uploaded else "Sample dataset loaded"

if data_source:
    with st.spinner("Cleaning and loading data…"):
        try:
            df, summary = data_cleaner.clean(data_source)
            st.session_state["data"] = df
            st.session_state["summary"] = summary
        except Exception as exc:
            st.error(f"Failed to load file: {exc}")
            st.stop()

    st.success(f"{source_label} — **{summary['rows_after']:,}** records ready for analysis.")

    # ── Cleaning summary metrics ──────────────────────────────────────────
    st.markdown("### Data Cleaning Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sheets / Files", summary["sheet_count"])
    m2.metric("Rows (before)", f"{summary['rows_before']:,}")
    m3.metric("Rows (after)", f"{summary['rows_after']:,}")
    m4.metric("Duplicates Removed", f"{summary['duplicates_removed']:,}")
    m5.metric("Blanks Fixed", f"{summary['blanks_fixed']:,}")

    # ── Columns detected ─────────────────────────────────────────────────
    with st.expander("Columns detected after normalisation"):
        cols = summary["columns_detected"]
        col_chunks = [cols[i : i + 4] for i in range(0, len(cols), 4)]
        for chunk in col_chunks:
            st.markdown("  ·  ".join(f"`{c}`" for c in chunk))

    # ── Data preview ─────────────────────────────────────────────────────
    st.markdown("### Data Preview")
    st.dataframe(df.head(50), use_container_width=True)

    # ── Navigation hint ───────────────────────────────────────────────────
    st.info(
        "Your data is loaded. Use the sidebar to navigate to:\n"
        "- **Compliance Dashboard** – KPIs, tax-gap charts, filing status\n"
        "- **Audit Risk Scoring** – ranked list of high-risk taxpayers\n"
        "- **Industry Benchmarking** – compare businesses within each industry"
    )

if not data_source:
    # ── Placeholder instructions ──────────────────────────────────────────
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("#### 📊 Compliance Dashboard")
        st.markdown(
            "Track overall tax gaps, filing status breakdowns, "
            "and compliance rates across industries and cities."
        )
    with col_b:
        st.markdown("#### 🎯 Audit Risk Scoring")
        st.markdown(
            "Statistically rank taxpayers by audit risk using "
            "z-scores, revenue ratios, and filing behaviour."
        )
    with col_c:
        st.markdown("#### 🏭 Industry Benchmarking")
        st.markdown(
            "Compare individual businesses against their industry "
            "peers and identify outliers likely to be underreporting."
        )

    st.markdown("---")
    st.markdown(
        "**Expected columns in your dataset:**\n\n"
        "| Column | Description |\n"
        "|---|---|\n"
        "| `Business_Name` | Taxpayer / business name |\n"
        "| `Industry` | Industry or sector |\n"
        "| `City` | Municipality |\n"
        "| `Tax_Year` | Fiscal year |\n"
        "| `Tax_Type` | e.g. Corporate Excise, Sales Tax |\n"
        "| `Reported_Revenue` | Revenue declared by taxpayer |\n"
        "| `Industry_Avg_Revenue` | Benchmark revenue for that industry |\n"
        "| `Tax_Paid` | Amount actually paid |\n"
        "| `Expected_Tax` | Tax owed based on revenue |\n"
        "| `Estimated_Tax_Gap` | Expected – Paid (auto-derived if missing) |\n"
        "| `Revenue_Ratio` | Reported / Industry Avg (auto-derived if missing) |\n"
        "| `Filing_Status` | Filed / Late / Not Filed |\n"
        "| `Compliance_Flag` | Compliant / Non-Compliant / Under Review |\n"
        "| `Previously_Audited` | Yes / No |\n"
        "| `Prior_Audit_Result` | Clean / Fraud / Underpayment |\n"
    )
