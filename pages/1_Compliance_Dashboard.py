"""
pages/1_Compliance_Dashboard.py
--------------------------------
High-level KPIs and compliance charts for the MA DOR analytics tool.
All charts are driven by the filters in the sidebar.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(
    page_title="Compliance Dashboard · MA DOR",
    page_icon="📊",
    layout="wide",
)

# ── Custom CSS (same palette as app.py) ──────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { background-color: #f0f4f8; }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 18px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #64748b; }
    [data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; color: #1e3a5f; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Guard: data must be loaded first ────────────────────────────────────────
if "data" not in st.session_state:
    st.warning("No data loaded. Please upload a file on the **Home** page first.")
    st.stop()

df_raw: pd.DataFrame = st.session_state["data"].copy()

# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.header("Filters")


def _multiselect_all(label: str, col: str, df: pd.DataFrame):
    options = sorted(df[col].dropna().unique().tolist()) if col in df.columns else []
    selected = st.sidebar.multiselect(label, options, default=options)
    return selected if selected else options


years    = _multiselect_all("Tax Year",   "Tax_Year",  df_raw)
ttypes   = _multiselect_all("Tax Type",   "Tax_Type",  df_raw)
inds     = _multiselect_all("Industry",   "Industry",  df_raw)
cities   = _multiselect_all("City",       "City",      df_raw)

df = df_raw.copy()
if "Tax_Year"  in df.columns: df = df[df["Tax_Year"].isin(years)]
if "Tax_Type"  in df.columns: df = df[df["Tax_Type"].isin(ttypes)]
if "Industry"  in df.columns: df = df[df["Industry"].isin(inds)]
if "City"      in df.columns: df = df[df["City"].isin(cities)]

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("## 📊 Compliance Dashboard")
st.markdown(f"Showing **{len(df):,}** records after filters.")
st.markdown("---")

# ── KPI helpers ───────────────────────────────────────────────────────────────
def _col(name):
    return df[name] if name in df.columns else pd.Series(dtype=float)


total_paid   = _col("Tax_Paid").sum()
total_gap    = _col("Estimated_Tax_Gap").sum()

# Suspicious = non-compliant OR tax gap > 0
if "Compliance_Flag" in df.columns:
    suspicious = df["Compliance_Flag"].str.lower().isin(
        ["non-compliant", "non_compliant", "noncompliant", "suspicious", "under review"]
    ).sum()
else:
    suspicious = int((_col("Estimated_Tax_Gap") > 0).sum())

if "Filing_Status" in df.columns:
    non_filers = df["Filing_Status"].str.lower().isin(
        ["not filed", "not_filed", "notfiled", "non-filer"]
    ).sum()
else:
    non_filers = 0

# ── KPI cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Tax Paid",        f"${total_paid:,.0f}")
k2.metric("Total Estimated Tax Gap", f"${total_gap:,.0f}")
k3.metric("Suspicious Cases",      f"{suspicious:,}")
k4.metric("Non-Filers",            f"{non_filers:,}")

st.markdown("---")

# ── Chart colour palette ─────────────────────────────────────────────────────
COLORS = px.colors.qualitative.Safe

# ── Row 1: Tax Gap by Industry  &  Tax Gap by City ───────────────────────────
row1_left, row1_right = st.columns(2)

with row1_left:
    st.subheader("Tax Gap by Industry")
    if "Industry" in df.columns and "Estimated_Tax_Gap" in df.columns:
        gap_ind = (
            df.groupby("Industry")["Estimated_Tax_Gap"]
            .sum()
            .reset_index()
            .sort_values("Estimated_Tax_Gap", ascending=False)
        )
        fig = px.bar(
            gap_ind,
            x="Industry",
            y="Estimated_Tax_Gap",
            labels={"Estimated_Tax_Gap": "Tax Gap ($)"},
            color="Estimated_Tax_Gap",
            color_continuous_scale="Reds",
            template="plotly_white",
        )
        fig.update_layout(
            coloraxis_showscale=False,
            xaxis_tickangle=-30,
            yaxis_tickformat="$,.0f",
            margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Industries with the tallest bars have the largest unpaid tax obligations — these sectors should be the first priority when allocating audit resources.")
    else:
        st.info("Industry or Tax Gap column not found.")

with row1_right:
    st.subheader("Top 10 Cities by Tax Gap")
    if "City" in df.columns and "Estimated_Tax_Gap" in df.columns:
        gap_city = (
            df.groupby("City")["Estimated_Tax_Gap"]
            .sum()
            .reset_index()
            .sort_values("Estimated_Tax_Gap", ascending=False)
            .head(10)
        )
        fig = px.bar(
            gap_city,
            x="City",
            y="Estimated_Tax_Gap",
            labels={"Estimated_Tax_Gap": "Tax Gap ($)"},
            color="Estimated_Tax_Gap",
            color_continuous_scale="Oranges",
            template="plotly_white",
        )
        fig.update_layout(
            coloraxis_showscale=False,
            xaxis_tickangle=-30,
            yaxis_tickformat="$,.0f",
            margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The top 10 cities driving the highest tax gaps — concentrating field audit efforts in these locations offers the greatest revenue recovery potential.")
    else:
        st.info("City or Tax Gap column not found.")

# ── Row 2: Compliance Flag pie  &  Tax Gap trend ─────────────────────────────
row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("Compliance Flag Breakdown")
    if "Compliance_Flag" in df.columns:
        flag_counts = df["Compliance_Flag"].value_counts().reset_index()
        flag_counts.columns = ["Compliance_Flag", "Count"]
        fig = px.pie(
            flag_counts,
            names="Compliance_Flag",
            values="Count",
            hole=0.42,
            color_discrete_sequence=["#22c55e", "#ef4444", "#f59e0b", "#64748b"],
            template="plotly_white",
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=True, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The share of compliant versus non-compliant businesses in the current filtered view. Each non-compliant or under-review case represents a potential revenue recovery opportunity.")
    else:
        st.info("Compliance_Flag column not found.")

with row2_right:
    st.subheader("Tax Gap Trend by Year")
    if "Tax_Year" in df.columns and "Estimated_Tax_Gap" in df.columns:
        gap_year = (
            df.groupby("Tax_Year")["Estimated_Tax_Gap"]
            .sum()
            .reset_index()
            .sort_values("Tax_Year")
        )
        fig = px.line(
            gap_year,
            x="Tax_Year",
            y="Estimated_Tax_Gap",
            markers=True,
            labels={"Estimated_Tax_Gap": "Total Tax Gap ($)", "Tax_Year": "Year"},
            template="plotly_white",
            color_discrete_sequence=["#1e3a5f"],
        )
        fig.update_layout(
            yaxis_tickformat="$,.0f",
            margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("A rising line indicates the tax gap is growing year over year — a sustained upward trend suggests enforcement activity has not kept pace with non-compliance.")
    else:
        st.info("Tax_Year or Estimated_Tax_Gap column not found.")

# ── Row 3: Filing Status distribution ────────────────────────────────────────
st.subheader("Filing Status Distribution")
if "Filing_Status" in df.columns:
    status_counts = df["Filing_Status"].value_counts().reset_index()
    status_counts.columns = ["Filing_Status", "Count"]
    palette = {
        "Filed":     "#22c55e",
        "Late":      "#f59e0b",
        "Not Filed": "#ef4444",
        "Not_Filed": "#ef4444",
    }
    colors = [palette.get(s, "#64748b") for s in status_counts["Filing_Status"]]
    fig = px.bar(
        status_counts,
        x="Filing_Status",
        y="Count",
        labels={"Filing_Status": "Filing Status", "Count": "Number of Taxpayers"},
        template="plotly_white",
        color="Filing_Status",
        color_discrete_sequence=colors,
    )
    fig.update_layout(showlegend=False, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Late filers and non-filers carry a higher risk of underpayment. A large red or amber bar is a signal that proactive outreach or enforcement notices should be issued.")
else:
    st.info("Filing_Status column not found.")
