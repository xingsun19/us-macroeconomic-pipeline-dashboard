"""Independent Streamlit dashboard: every observation is read from SQLite."""

from datetime import date
import json
import os
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from macro_pipeline.config import Settings
from macro_pipeline.db import read_dataset

st.set_page_config(page_title="Macro Observatory | U.S. Economy", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background: #f7f9fa;}
.block-container {padding-top: 4rem; max-width: 1480px;}
[data-testid="stSidebar"] {background: #142c3a;}
[data-testid="stSidebar"] * {color: #eff6f8;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color: #142c3a;}
[data-testid="stMetric"] {background: white; border: 1px solid #dce5e8; border-radius: 12px; padding: 20px 22px;}
[data-testid="stMetricValue"] {font-family: Georgia, serif; color: #142c3a;}
.eyebrow {font-size: .76rem; font-weight: 700; letter-spacing: .18em; color: #008c95;}
.intro {font-size: 1.05rem; color: #566c78; max-width: 850px;}
h1, h2, h3 {color: #142c3a;}
</style>""", unsafe_allow_html=True)

LABELS = {"unrate": "Unemployment rate", "cpiaucsl": "Consumer price index", "fedfunds": "Federal funds rate", "cpi_yoy": "CPI inflation · YoY", "cpi_mom": "CPI inflation · MoM", "real_rate_proxy": "Ex-post real-rate proxy"}
UNITS = {"unrate": "%", "cpiaucsl": "Index · 1982–84 = 100", "fedfunds": "%", "cpi_yoy": "% YoY", "cpi_mom": "% MoM", "real_rate_proxy": "percentage points"}
PALETTE = ["#008c95", "#d68b29", "#5669b3", "#b56473", "#4a806c", "#647c8b"]
CHART_CONFIG = {"scrollZoom": True, "displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 2}}


@st.cache_data(ttl=60)
def load_data(path):
    return read_dataset(path)


settings = Settings.from_env()
with st.sidebar:
    st.markdown("### ◈ Macro Observatory")
    st.caption("U.S. ECONOMIC MONITOR")
    if st.button("Refresh database", use_container_width=True):
        load_data.clear()
try:
    data, run = load_data(str(settings.db_path))
except (OSError, ValueError, sqlite3.Error):
    st.title("Macro Observatory")
    st.info("The database has not been initialized. Run `macro-pipeline update` to load FRED observations, then refresh this page.")
    st.stop()

with st.sidebar:
    st.divider()
    st.markdown("**Display options**")
    min_date, max_date = data.index.min().date(), data.index.max().date()
    selected = st.multiselect("Indicators", list(LABELS), default=["unrate", "cpiaucsl", "fedfunds"], format_func=lambda x: LABELS[x], key="indicators")
    mode = st.radio("Trend comparison", ["Original units", "Standardized (z-score)"], key="comparison")
    st.caption("Standardization uses the full history. Each series is centered and scaled to its own standard deviation.")
    st.divider()
    st.caption(f"FRED vintage: {run['as_of']}\n\nMonthly data · January 2000 onward\n\nSource: Federal Reserve Bank of St. Louis")

st.markdown('<div class="eyebrow">RESEARCH DESK / UNITED STATES</div>', unsafe_allow_html=True)
st.title("The economy, in perspective.")
if os.getenv("MACRO_OFFLINE") == "1":
    st.info(f"Archived snapshot · FRED vintage {run['as_of']}. Offline reproduction; these are historical results, not a live update.")
st.markdown('<p class="intro">Explore the relationship between jobs, prices, and monetary policy. The full history of three defining U.S. economic indicators, from 2000 onward.</p>', unsafe_allow_html=True)
st.caption(f"Validated dataset · {len(data):,} monthly rows · Published {pd.Timestamp(run['published_at']).strftime('%Y-%m-%d %H:%M UTC')}")
st.markdown("#### Latest available observations")
for container, col in zip(st.columns(3), ["unrate", "cpiaucsl", "fedfunds"]):
    observed = data[col].dropna()
    last = observed.iloc[-1]
    # Never compare non-adjacent months as a monthly change.
    previous = data[col].shift(1).loc[observed.index[-1]]
    unit = "index points" if col == "cpiaucsl" else "pp"
    delta = f"{last - previous:+.2f} {unit} MoM" if pd.notna(previous) else None
    with container:
        st.metric(LABELS[col], f"{last:.2f}" + ("%" if col != "cpiaucsl" else ""), delta=delta, delta_color="off")
        st.caption(f"{observed.index[-1]:%B %Y} · {UNITS[col]}")
st.caption("Charts, correlations, and CSV downloads include the full available history. Publication months differ by series.")
if os.getenv("MACRO_OFFLINE") != "1" and (pd.Timestamp(date.today()) - pd.Timestamp(run["as_of"])).days > 7:
    st.warning("This snapshot is more than seven days old. Start the project with Run.command to check for new releases.")

if not selected:
    st.info("Select at least one indicator in the sidebar.")
    st.stop()

overview, relations, table = st.tabs(["Historical trends", "Relationships", "Data & quality"])
with overview:
    st.subheader("Follow the long view")
    st.caption(f"{min_date:%B %Y} — {max_date:%B %Y} · Full history · {len(data):,} monthly observations.")
    if mode == "Original units":
        fig = make_subplots(rows=len(selected), cols=1, shared_xaxes=True, subplot_titles=[f"{LABELS[c]} · {UNITS[c]}" for c in selected], vertical_spacing=min(.09, .4 / len(selected)))
        for i, col in enumerate(selected):
            fig.add_trace(go.Scatter(x=data.index, y=data[col], name=LABELS[col], line={"color": PALETTE[i], "width": 2.3}, connectgaps=False, hovertemplate="%{x|%b %Y}<br>%{y:.2f}<extra>%{fullData.name}</extra>"), row=i+1, col=1)
        fig.update_layout(height=max(350, 245 * len(selected)), showlegend=False)
    else:
        std = data[selected].std(ddof=0).replace(0, np.nan)
        normalized = (data[selected] - data[selected].mean()) / std
        unusable = std[std.isna()].index.tolist()
        if unusable:
            st.info("Constant or empty series cannot be standardized: " + ", ".join(LABELS[c] for c in unusable))
        fig = px.line(normalized.rename(columns=LABELS), color_discrete_sequence=PALETTE, labels={"value": "Standard deviations from full-history mean", "date": "", "variable": "Indicator"}, height=530)
        fig.add_hline(y=0, line_width=1, line_color="#cedadd")
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white", font={"family": "Arial", "color": "#243e4c"}, margin={"l": 25, "r": 25, "t": 45, "b": 20}, hovermode="x unified", legend={"orientation": "h", "y": 1.12})
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG, key="trend_chart")
    st.caption("CPI is a price-level index. Select CPI inflation to compare growth in prices with rates. Missing values remain gaps; no values are interpolated.")

with relations:
    st.subheader("How do the indicators move together?")
    controls = st.columns(3)
    xcol = controls[0].selectbox("Horizontal axis", list(LABELS), index=0, format_func=lambda x: LABELS[x], key="x_indicator")
    ycol = controls[1].selectbox("Vertical axis", list(LABELS), index=3, format_func=lambda x: LABELS[x], key="y_indicator")
    lag = controls[2].slider("Outcome lag (months)", 0, 24, 0, key="lag")
    # Shift on the complete monthly grid before dropping nulls.
    pairs = pd.DataFrame({"x": data[xcol], "y": data[ycol].shift(-lag)}, index=data.index).dropna()
    if len(pairs) >= 3 and pairs.x.nunique() > 1 and pairs.y.nunique() > 1:
        pairs["Year"] = pairs.index.year
        pairs["Month"] = pairs.index.strftime("%Y-%m")
        scatter = px.scatter(pairs, x="x", y="y", color="Year", hover_data=["Month"], color_continuous_scale="Teal", labels={"x": f"{LABELS[xcol]} at t ({UNITS[xcol]})", "y": f"{LABELS[ycol]} at t+{lag} ({UNITS[ycol]})"}, height=450)
        scatter.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(scatter, use_container_width=True, config=CHART_CONFIG, key="scatter_chart")
        st.caption(f"Pearson r = {pairs.x.corr(pairs.y):.3f} · {len(pairs)} matched months. Positive lag pairs the horizontal series at month t with the vertical series at month t + lag, using the full available history.")
    else:
        st.info("At least three paired observations with variation are needed. Try different indicators.")
    correlation_mode = st.radio("Correlation transformation", ["Levels", "Monthly changes"], horizontal=True, key="correlation_mode")
    corr_data = data[selected] if correlation_mode == "Levels" else data[selected].diff()
    if len(selected) > 1 and len(corr_data) >= 3:
        corr = corr_data.corr(min_periods=3).rename(index=LABELS, columns=LABELS)
        heat = px.imshow(corr, zmin=-1, zmax=1, color_continuous_scale="BrBG", text_auto=".2f", aspect="auto", height=380)
        heat.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(heat, use_container_width=True, config=CHART_CONFIG, key="correlation_chart")
        st.caption("Pairwise-complete Pearson correlations. Sample sizes may differ when recent releases are missing.")
    st.info("These are descriptive associations. Trends, autocorrelation, policy responses, and structural changes can drive correlations. Lagged association does not establish causation.")

with table:
    st.subheader("Transparent data, from source to chart")
    download = data[[*selected, "unrate_status", "cpiaucsl_status", "fedfunds_status"]]
    st.download_button("Download full history · CSV", data=download.to_csv(index_label="date").encode("utf-8"), file_name=f"us_macro_{min_date}_{max_date}.csv", mime="text/csv", key="download_csv")
    st.dataframe(download, use_container_width=True)
    st.markdown("**Quality policy.** Source `.` values are stored as null and flagged. Omitted calendar months, invalid values, or more than 5% source-missing observations block publication. Unreleased trailing months remain null. No forward-fill, interpolation, or fabricated observations. Raw responses and SHA-256 checksums are retained locally.")
    st.caption("The October 2025 unemployment and CPI observations are missing because of the federal government shutdown. Monthly changes touching this gap, and year-over-year changes using it as a base, remain unavailable.")
    quality = json.loads(run["validation_json"])
    for message in quality.get("warnings", []):
        st.caption(message)
    with st.expander("Published validation report"):
        st.json(quality)
    with st.expander("Definitions & source attribution"):
        st.markdown("""
- **UNRATE:** civilian unemployment rate, percent, seasonally adjusted. [BLS via FRED](https://fred.stlouisfed.org/series/UNRATE).
- **CPIAUCSL:** all-items urban CPI, index 1982–1984 = 100, seasonally adjusted. [BLS via FRED](https://fred.stlouisfed.org/series/CPIAUCSL).
- **FEDFUNDS:** effective federal funds rate, monthly average of daily figures, percent, not seasonally adjusted. [Federal Reserve via FRED](https://fred.stlouisfed.org/series/FEDFUNDS).
- **CPI YoY:** `100 × (CPI[t] / CPI[t−12] − 1)`; **CPI MoM:** `100 × (CPI[t] / CPI[t−1] − 1)`.
- **Ex-post real-rate proxy:** federal funds rate minus trailing CPI YoY inflation; it does not measure expected real returns.
""")
st.divider()
st.caption("Northwestern University · Topics in Data Engineering · Fall 2026 | FRED API → SQLite → Airflow → Python / Plotly")
