"""
pages/2_Audit_Risk_Scoring.py
------------------------------
Statistical audit-risk ranking using z-scores, revenue ratios, and
filing/audit-history signals.  No ML – purely statistical methods.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

st.set_page_config(
    page_title="Audit Risk Scoring · MA DOR",
    page_icon="🎯",
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

# ── Risk Score calculation ────────────────────────────────────────────────────
# We build a composite 0-100 score from four signal groups:
#
#  1. Revenue under-reporting (z-score of Revenue_Ratio per industry) – 35 pts
#  2. Absolute tax gap                                                  – 30 pts
#  3. Filing behaviour (not_filed=30, late=15, filed=0)                – 20 pts
#  4. Prior audit history (prior fraud=15, underpayment=10, else=0)    – 15 pts

def _zscore_clipped(series: pd.Series) -> pd.Series:
    """Return z-scores clipped to [-3, 3] then rescaled to [0, 1].
    A LOWER Revenue_Ratio → HIGHER z-score risk (inversion applied).
    """
    s = series.copy().astype(float)
    if s.std() == 0 or s.isna().all():
        return pd.Series(0.5, index=s.index)
    z = stats.zscore(s.fillna(s.median()))
    z_clipped = np.clip(z, -3, 3)
    # Invert: low ratio = high risk
    z_inverted = -z_clipped
    # Rescale to [0, 1]
    z_min, z_max = z_inverted.min(), z_inverted.max()
    if z_max == z_min:
        return pd.Series(0.5, index=s.index)
    return (z_inverted - z_min) / (z_max - z_min)


# -- Signal 1: Revenue_Ratio z-score per industry (35 pts) -------------------
sig_revenue = pd.Series(0.0, index=df.index)
if "Revenue_Ratio" in df.columns and "Industry" in df.columns:
    for ind, grp in df.groupby("Industry"):
        sig_revenue.loc[grp.index] = _zscore_clipped(grp["Revenue_Ratio"]) * 35
elif "Revenue_Ratio" in df.columns:
    sig_revenue = _zscore_clipped(df["Revenue_Ratio"]) * 35


# -- Signal 2: Absolute tax gap (30 pts) -------------------------------------
sig_gap = pd.Series(0.0, index=df.index)
if "Estimated_Tax_Gap" in df.columns:
    gap = df["Estimated_Tax_Gap"].clip(lower=0).fillna(0)
    g_max = gap.quantile(0.99)
    if g_max > 0:
        sig_gap = (gap.clip(upper=g_max) / g_max) * 30


# -- Signal 3: Filing status (20 pts) ----------------------------------------
sig_filing = pd.Series(0.0, index=df.index)
if "Filing_Status" in df.columns:
    fs = df["Filing_Status"].str.lower().fillna("")
    sig_filing = fs.map(
        lambda s: 20 if "not" in s else (15 if "late" in s else 0)
    ).astype(float)


# -- Signal 4: Prior audit result (15 pts) ------------------------------------
sig_audit = pd.Series(0.0, index=df.index)
if "Prior_Audit_Result" in df.columns:
    par = df["Prior_Audit_Result"].str.lower().fillna("")
    sig_audit = par.map(
        lambda s: 15 if "fraud" in s else (10 if "underpay" in s else 0)
    ).astype(float)
elif "Previously_Audited" in df.columns:
    pa = df["Previously_Audited"].str.lower().fillna("")
    sig_audit = pa.map(lambda s: 5 if "yes" in s else 0).astype(float)


# -- Composite risk score -----------------------------------------------------
df["_sig_revenue"] = sig_revenue
df["_sig_gap"]     = sig_gap
df["_sig_filing"]  = sig_filing
df["_sig_audit"]   = sig_audit
df["Risk_Score"]   = (
    df["_sig_revenue"] + df["_sig_gap"] + df["_sig_filing"] + df["_sig_audit"]
).clip(0, 100).round(1)


def _risk_band(score):
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"

df["Risk_Band"] = df["Risk_Score"].apply(_risk_band)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("## 🎯 Audit Risk Scoring")
st.markdown(
    "Taxpayers are ranked by a composite **Risk Score (0–100)** built from "
    "four statistical signals: revenue under-reporting, absolute tax gap, "
    "filing behaviour, and prior audit history."
)
st.markdown("---")

# ── KPI cards ─────────────────────────────────────────────────────────────────
top100 = df.nlargest(100, "Risk_Score")
recoverable = top100["Estimated_Tax_Gap"].sum() if "Estimated_Tax_Gap" in df.columns else 0
high_risk    = int((df["Risk_Band"] == "High").sum())
avg_score    = df["Risk_Score"].mean()

k1, k2, k3 = st.columns(3)
k1.metric("Est. Recoverable Revenue (Top 100)", f"${recoverable:,.0f}")
k2.metric("High-Risk Cases (Score ≥ 70)",       f"{high_risk:,}")
k3.metric("Average Risk Score",                 f"{avg_score:.1f} / 100")

st.markdown("---")

# ── Factor contribution chart ────────────────────────────────────────────────
st.subheader("Average Contribution by Risk Factor")
factor_data = pd.DataFrame({
    "Factor": [
        "Revenue Under-Reporting (35 pts max)",
        "Absolute Tax Gap (30 pts max)",
        "Late / Non-Filing (20 pts max)",
        "Prior Audit Result (15 pts max)",
    ],
    "Avg Contribution": [
        df["_sig_revenue"].mean(),
        df["_sig_gap"].mean(),
        df["_sig_filing"].mean(),
        df["_sig_audit"].mean(),
    ],
})
factor_data = factor_data.sort_values("Avg Contribution")

fig_factors = px.bar(
    factor_data,
    x="Avg Contribution",
    y="Factor",
    orientation="h",
    labels={"Avg Contribution": "Average Points Contributed"},
    template="plotly_white",
    color="Avg Contribution",
    color_continuous_scale="Blues",
)
fig_factors.update_layout(
    coloraxis_showscale=False,
    margin=dict(t=10, b=10),
    height=260,
)
st.plotly_chart(fig_factors, use_container_width=True)
st.caption("This shows which risk signal is driving scores most across all taxpayers. A long bar for 'Late / Non-Filing' means filing behaviour — not revenue under-reporting — is the primary concern in the current dataset.")

st.markdown("---")

# ── Flagged taxpayer table ────────────────────────────────────────────────────
st.subheader("Flagged Taxpayers — Ranked by Risk Score")

# Choose display columns that actually exist
display_priority = [
    "Business_Name", "Taxpayer_ID", "Industry", "City", "Tax_Year", "Tax_Type",
    "Risk_Score", "Risk_Band",
    "Estimated_Tax_Gap", "Revenue_Ratio",
    "Filing_Status", "Compliance_Flag",
    "Previously_Audited", "Prior_Audit_Result",
]
display_cols = [c for c in display_priority if c in df.columns]

# Colour filter toggle
band_filter = st.radio(
    "Show risk band",
    ["All", "High", "Medium", "Low"],
    horizontal=True,
)

view = df.sort_values("Risk_Score", ascending=False)
if band_filter != "All":
    view = view[view["Risk_Band"] == band_filter]
view = view[display_cols].head(500)

# Build column_config for st.dataframe
col_config = {
    "Risk_Score": st.column_config.ProgressColumn(
        "Risk Score",
        min_value=0,
        max_value=100,
        format="%.1f",
    ),
}
if "Estimated_Tax_Gap" in view.columns:
    col_config["Estimated_Tax_Gap"] = st.column_config.NumberColumn(
        "Est. Tax Gap",
        format="$%,.0f",
    )
if "Revenue_Ratio" in view.columns:
    col_config["Revenue_Ratio"] = st.column_config.NumberColumn(
        "Revenue Ratio",
        format="%.3f",
    )
if "Risk_Band" in view.columns:
    col_config["Risk_Band"] = st.column_config.TextColumn("Risk Band")

st.dataframe(
    view,
    use_container_width=True,
    height=500,
    column_config=col_config,
)

st.caption(
    "Taxpayers are ranked by a composite score based on how far below their industry peers they report revenue, "
    "their estimated unpaid tax, filing behaviour, and any prior audit findings. "
    "High-risk cases (score ≥ 70) should be prioritised for immediate audit selection."
)
