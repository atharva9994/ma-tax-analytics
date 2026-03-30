"""
pages/3_Industry_Benchmarking.py
---------------------------------
Drill into a single industry and compare businesses against their peers.
Outliers (Revenue_Ratio < 0.6) are highlighted separately.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Industry Benchmarking · MA DOR",
    page_icon="🏭",
    layout="wide",
)

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

# ── Guard ────────────────────────────────────────────────────────────────────
if "data" not in st.session_state:
    st.warning("No data loaded. Please upload a file on the **Home** page first.")
    st.stop()

df: pd.DataFrame = st.session_state["data"].copy()

if "Industry" not in df.columns:
    st.error("Dataset does not contain an `Industry` column.")
    st.stop()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("## 🏭 Industry Benchmarking")
st.markdown(
    "Select an industry below to compare all businesses in that sector against "
    "each other. Businesses reporting less than **60 %** of their industry's "
    "average revenue are flagged as potential underreporters."
)
st.markdown("---")

# ── Industry selector ─────────────────────────────────────────────────────────
industries = sorted(df["Industry"].dropna().unique().tolist())
selected_industry = st.selectbox("Select an industry to drill into", industries)

ind_df = df[df["Industry"] == selected_industry].copy()

# ── Compute Industry_Avg_Revenue if absent ────────────────────────────────────
if "Industry_Avg_Revenue" not in ind_df.columns and "Reported_Revenue" in ind_df.columns:
    ind_avg = ind_df["Reported_Revenue"].mean()
    ind_df["Industry_Avg_Revenue"] = ind_avg

if "Revenue_Ratio" not in ind_df.columns and "Reported_Revenue" in ind_df.columns:
    ind_df["Revenue_Ratio"] = (
        ind_df["Reported_Revenue"] / ind_df["Industry_Avg_Revenue"].replace(0, np.nan)
    )

# ── KPI cards ─────────────────────────────────────────────────────────────────
n_businesses  = len(ind_df)
avg_revenue   = ind_df["Reported_Revenue"].mean()  if "Reported_Revenue"  in ind_df.columns else 0
med_revenue   = ind_df["Reported_Revenue"].median() if "Reported_Revenue" in ind_df.columns else 0

if "Compliance_Flag" in ind_df.columns:
    n_compliant    = ind_df["Compliance_Flag"].str.lower().str.contains("compliant").sum()
    compliance_pct = (n_compliant / n_businesses * 100) if n_businesses > 0 else 0
else:
    compliance_pct = np.nan

k1, k2, k3, k4 = st.columns(4)
k1.metric("Businesses in Industry",  f"{n_businesses:,}")
k2.metric("Average Revenue",         f"${avg_revenue:,.0f}")
k3.metric("Median Revenue",          f"${med_revenue:,.0f}")
k4.metric("Compliance Rate",         f"{compliance_pct:.1f}%" if not np.isnan(compliance_pct) else "N/A")

st.markdown("---")

# ── Row 1: Box plot  &  Scatter (Reported vs Industry Avg) ───────────────────
row1_l, row1_r = st.columns(2)

with row1_l:
    st.subheader(f"Revenue Distribution — {selected_industry}")
    if "Reported_Revenue" in ind_df.columns:
        fig = px.box(
            ind_df,
            y="Reported_Revenue",
            points="all",
            labels={"Reported_Revenue": "Reported Revenue ($)"},
            template="plotly_white",
            color_discrete_sequence=["#1e3a5f"],
        )
        fig.update_layout(yaxis_tickformat="$,.0f", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The box shows the typical revenue range for businesses in this industry. Dots above or below the whiskers are outliers — businesses reporting unusually high or suspiciously low revenue compared to their peers.")
    else:
        st.info("Reported_Revenue column not found.")

with row1_r:
    st.subheader("Reported vs Industry Average Revenue")
    if {"Reported_Revenue", "Industry_Avg_Revenue"}.issubset(ind_df.columns):
        plot_df = ind_df.copy()
        plot_df["_under"] = plot_df["Revenue_Ratio"] < 0.6
        plot_df["Category"] = np.where(plot_df["_under"], "Underreporter (< 60%)", "Within Range")

        # Reference diagonal
        axis_max = max(
            plot_df["Reported_Revenue"].max(),
            plot_df["Industry_Avg_Revenue"].max(),
        ) * 1.05

        fig = px.scatter(
            plot_df,
            x="Industry_Avg_Revenue",
            y="Reported_Revenue",
            color="Category",
            color_discrete_map={
                "Underreporter (< 60%)": "#ef4444",
                "Within Range": "#22c55e",
            },
            hover_data=[c for c in ["Business_Name", "City", "Revenue_Ratio"] if c in plot_df.columns],
            labels={
                "Industry_Avg_Revenue": "Industry Avg Revenue ($)",
                "Reported_Revenue": "Reported Revenue ($)",
            },
            template="plotly_white",
        )
        # Diagonal line y = x
        fig.add_shape(
            type="line",
            x0=0, y0=0, x1=axis_max, y1=axis_max,
            line=dict(color="#64748b", dash="dash", width=1.5),
        )
        fig.add_annotation(
            x=axis_max * 0.75, y=axis_max * 0.85,
            text="Expected (y = x)",
            showarrow=False,
            font=dict(color="#64748b", size=11),
        )
        fig.update_layout(
            xaxis_tickformat="$,.0f",
            yaxis_tickformat="$,.0f",
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each dot is a business. Dots on or near the dashed line are reporting in line with the industry average. Red dots below the line are reporting significantly less than expected and warrant a closer look.")
    else:
        st.info("Reported_Revenue or Industry_Avg_Revenue column not found.")

st.markdown("---")

# ── Outlier table ─────────────────────────────────────────────────────────────
st.subheader(f"Potential Underreporters in {selected_industry} (Revenue Ratio < 0.60)")

if "Revenue_Ratio" in ind_df.columns:
    outliers = ind_df[ind_df["Revenue_Ratio"] < 0.6].copy()
    if len(outliers) == 0:
        st.success("No businesses in this industry have a Revenue Ratio below 0.60.")
    else:
        display_priority = [
            "Business_Name", "Taxpayer_ID", "City", "Tax_Year",
            "Reported_Revenue", "Industry_Avg_Revenue", "Revenue_Ratio",
            "Tax_Paid", "Expected_Tax", "Estimated_Tax_Gap",
            "Filing_Status", "Compliance_Flag",
        ]
        display_cols = [c for c in display_priority if c in outliers.columns]
        outliers = outliers[display_cols].sort_values("Revenue_Ratio")

        col_config = {}
        if "Revenue_Ratio" in outliers.columns:
            col_config["Revenue_Ratio"] = st.column_config.NumberColumn(
                "Revenue Ratio", format="%.3f"
            )
        for money_col in ["Reported_Revenue", "Industry_Avg_Revenue",
                          "Tax_Paid", "Expected_Tax", "Estimated_Tax_Gap"]:
            if money_col in outliers.columns:
                col_config[money_col] = st.column_config.NumberColumn(
                    money_col.replace("_", " "), format="$%,.0f"
                )

        st.markdown(f"**{len(outliers)} businesses** flagged as potential underreporters.")
        st.dataframe(outliers, use_container_width=True, column_config=col_config)
        st.caption("These businesses report less than 60% of what a typical business in their industry reports. The lower the Revenue Ratio, the larger the potential gap between what was declared and what was likely earned.")
else:
    st.info("Revenue_Ratio column not available.")

st.markdown("---")

# ── Cross-industry compliance comparison ─────────────────────────────────────
st.subheader("Compliance Rate Across All Industries")

if "Compliance_Flag" in df.columns:
    comp_data = []
    for ind in sorted(df["Industry"].dropna().unique()):
        idf = df[df["Industry"] == ind]
        total = len(idf)
        n_comp = idf["Compliance_Flag"].str.lower().str.contains("compliant").sum()
        n_non  = total - n_comp
        comp_data.append({
            "Industry":   ind,
            "Compliant":  n_comp,
            "Non-Compliant": n_non,
            "Compliance Rate (%)": round(n_comp / total * 100, 1) if total else 0,
        })
    comp_df = pd.DataFrame(comp_data).sort_values("Compliance Rate (%)", ascending=False)

    fig = px.bar(
        comp_df,
        x="Industry",
        y=["Compliant", "Non-Compliant"],
        barmode="group",
        labels={"value": "Number of Businesses", "variable": "Status"},
        template="plotly_white",
        color_discrete_map={
            "Compliant":     "#22c55e",
            "Non-Compliant": "#ef4444",
        },
    )
    fig.update_layout(
        xaxis_tickangle=-30,
        legend_title_text="",
        margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Industries with a large red bar relative to their green bar have a compliance problem. These sectors may benefit from targeted outreach campaigns or industry-specific audit initiatives.")

    # Compliance rate line overlay
    fig2 = px.bar(
        comp_df,
        x="Industry",
        y="Compliance Rate (%)",
        labels={"Compliance Rate (%)": "Compliance Rate (%)"},
        template="plotly_white",
        color="Compliance Rate (%)",
        color_continuous_scale="RdYlGn",
        text="Compliance Rate (%)",
    )
    fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig2.update_layout(
        xaxis_tickangle=-30,
        coloraxis_showscale=False,
        margin=dict(t=20, b=10),
        yaxis_range=[0, 110],
    )
    st.subheader("Compliance Rate % by Industry")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Industries shown in red have the lowest compliance rates and represent the greatest untapped revenue recovery. Green industries are largely self-compliant and require fewer audit resources.")
else:
    st.info("Compliance_Flag column not found — cannot compute compliance rates.")
