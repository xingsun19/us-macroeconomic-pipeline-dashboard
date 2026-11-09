"""Independent demographic page, reading the same validated SQLite publication."""

import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from macro_pipeline.config import Settings, RACE_SERIES
from macro_pipeline.db import read_race_dataset, RACE_COLUMNS, RACE_STATUS_COLUMNS
from macro_pipeline.demographics import GROUP_LABELS, GROUP_COLORS, CATEGORY_NOTE, CAUSAL_NOTE
from macro_pipeline.race_analysis import crisis_comparison, policy_correlations

st.set_page_config(page_title="Unemployment by Race & Ethnicity", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background: #f7f9fa;}
.block-container {padding-top: 3rem; max-width: 1480px;}
[data-testid="stMetric"] {background: white; border: 1px solid #dce5e8; border-radius: 12px; padding: 16px;}
h1, h2, h3 {color: #142c3a;}
</style>""", unsafe_allow_html=True)
CHART_CONFIG = {"scrollZoom": True, "displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 2}}


@st.cache_data(ttl=60)
def load_demographics(path):
    return read_race_dataset(path)


settings = Settings.from_env()
st.title("Unemployment by Race & Ethnicity")
st.caption("U.S. LABOR MARKET · MONTHLY · SEASONALLY ADJUSTED · JANUARY 2003 ONWARD")
with st.sidebar:
    st.markdown("### ◈ Macro Observatory")
    if st.button("Refresh database", key="race_refresh", use_container_width=True):
        load_demographics.clear()
try:
    data, run = load_demographics(str(settings.db_path))
except (OSError, ValueError, sqlite3.Error):
    st.info("Race and ethnicity data are not available in this database yet. Run `macro-pipeline update` or the updated Run.command, then refresh. For offline use, prepare the updated image and replay the current seven-series archive.")
    st.stop()

if os.getenv("MACRO_OFFLINE") == "1":
    st.info(f"Archived snapshot · FRED vintage {run['as_of']}. Offline reproduction; no live API update.")
st.caption(f"FRED vintage {run['as_of']} · {len(data)} monthly rows · Published {pd.Timestamp(run['published_at']).strftime('%Y-%m-%d %H:%M UTC')}")
st.info(CATEGORY_NOTE)

st.subheader("Latest available observations")
st.caption("These cards use the full dataset. The time-range controls below apply to charts, summaries, and downloads.")
for container, col in zip(st.columns(4), RACE_COLUMNS):
    observed = data[col].dropna()
    latest = observed.index[-1]
    previous = data[col].shift(1).loc[latest]
    delta = f"{observed.iloc[-1] - previous:+.1f} pp MoM" if pd.notna(previous) else None
    with container:
        st.metric(GROUP_LABELS[col], f"{observed.iloc[-1]:.1f}%", delta, delta_color="off")
        st.caption(f"{latest:%B %Y}")

minimum, maximum = data.index.min(), data.index.max()
with st.sidebar:
    st.divider()
    selected = st.multiselect("Groups", RACE_COLUMNS, default=RACE_COLUMNS, format_func=lambda x: GROUP_LABELS[x], key="race_groups")
    period = st.selectbox("Time range", ["Full history", "Last 5 years", "Financial crisis (2007–2010)", "Pandemic (2019–2021)", "Custom dates"], key="race_period")
    start, end = minimum, maximum
    if period == "Last 5 years":
        start = max(minimum, maximum - pd.DateOffset(months=59))
    elif period == "Financial crisis (2007–2010)":
        start, end = pd.Timestamp("2007-01-01"), pd.Timestamp("2010-12-01")
    elif period == "Pandemic (2019–2021)":
        start, end = pd.Timestamp("2019-01-01"), pd.Timestamp("2021-12-01")
    elif period == "Custom dates":
        dates = st.date_input("Date range", value=(minimum.date(), maximum.date()), min_value=minimum.date(), max_value=maximum.date(), key="race_dates")
        if len(dates) != 2:
            st.info("Choose both a start date and an end date.")
            st.stop()
        start, end = [pd.Timestamp(d).replace(day=1) for d in dates]
    st.caption("Dates select whole calendar months. Missing values remain gaps; no interpolation.")
    st.caption("Refresh database reloads stored data. Use Run to request new FRED releases.")
if start > end:
    st.warning("The start month must be on or before the end month.")
    st.stop()
view = data.loc[start:end]
if view.empty:
    st.info("No observations are available in this time range.")
    st.stop()
st.caption(f"Selected period: {view.index.min():%B %Y}–{view.index.max():%B %Y} · {len(view)} calendar months")

trends, gap_tab, policy_tab = st.tabs(["Group trends", "Black–White gap", "Policy & data"])
with trends:
    if selected:
        figure = go.Figure()
        for col in selected:
            figure.add_trace(go.Scatter(x=view.index, y=view[col], mode="lines", name=GROUP_LABELS[col],
                line={"color": GROUP_COLORS[col], "width": 2.4}, connectgaps=False,
                hovertemplate="%{x|%b %Y}<br>%{y:.1f}%<extra>%{fullData.name}</extra>"))
        figure.update_layout(template="plotly_white", height=480, yaxis_title="Unemployment rate (%)", hovermode="x unified", legend={"orientation": "h", "y": 1.15}, margin={"t": 45})
        st.plotly_chart(figure, use_container_width=True, config=CHART_CONFIG, key="race_trends")
        st.dataframe(view[selected].describe().T.rename(index=GROUP_LABELS), use_container_width=True)
    else:
        st.info("Select at least one group to draw trend lines.")
    with st.expander("Financial crisis and pandemic comparisons · fixed analysis windows"):
        st.caption("Financial crisis: December 2007 baseline, January 2008–December 2010 peak search. Pandemic: February 2020 baseline, March 2020–December 2021 peak search. This table uses the full dataset and is independent of the chart's selected range. Windows are descriptive, not official recession dates or causal estimates.")
        events = crisis_comparison(data)
        events["group"] = events.group.map(GROUP_LABELS)
        st.dataframe(events, use_container_width=True, hide_index=True)

with gap_tab:
    st.subheader("Black unemployment minus White unemployment")
    st.caption("A positive gap means the Black unemployment rate is higher. Units are percentage points, not percent change. Only same-month pairs are used.")
    observed = view.black_white_gap_pp.dropna()
    if len(observed):
        left, right = st.columns(2)
        left.metric("Last observed gap in selected range", f"{observed.iloc[-1]:.2f} pp")
        left.caption(f"{observed.index[-1]:%B %Y}")
        right.metric("Mean gap in selected range", f"{observed.mean():.2f} pp")
        right.caption(f"{len(observed)} paired months")
        figure = go.Figure(go.Scatter(x=view.index, y=view.black_white_gap_pp, mode="lines", name="Black–White gap", line={"color": GROUP_COLORS["black"], "width": 2.4}, connectgaps=False))
        figure.add_hline(y=0, line_width=1, line_color="#142c3a")
        figure.update_layout(template="plotly_white", height=400, yaxis_title="Gap (percentage points)")
        st.plotly_chart(figure, use_container_width=True, config=CHART_CONFIG, key="race_gap")
    else:
        st.info("No matched Black and White observations are available in the selected period.")

with policy_tab:
    st.subheader("Unemployment and the federal funds rate")
    x = st.selectbox("Outcome", [*RACE_COLUMNS, "black_white_gap_pp"], format_func=lambda c: GROUP_LABELS.get(c, "Black–White gap"), key="race_policy_outcome")
    transformation = st.radio("Transformation", ["Levels", "Monthly changes"], horizontal=True, key="race_policy_mode")
    # Compute differences before the date filter so calendar gaps retain their meaning.
    source = data if transformation == "Levels" else data.select_dtypes(include="number").diff()
    pairs = source.loc[start:end, ["fedfunds", x]].dropna()
    if len(pairs) >= 3 and pairs.fedfunds.nunique() > 1 and pairs[x].nunique() > 1:
        pairs = pairs.assign(Month=pairs.index.strftime("%Y-%m"), Year=pairs.index.year)
        unit = "pp" if transformation == "Monthly changes" or x == "black_white_gap_pp" else "%"
        fig = px.scatter(pairs, x="fedfunds", y=x, color="Year", hover_data=["Month"], color_continuous_scale="Teal", labels={"fedfunds": "Federal funds rate" + (" change (pp)" if transformation == "Monthly changes" else " (%)"), x: f"{GROUP_LABELS.get(x, 'Black–White gap')} ({unit})"}, height=400)
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG, key="race_policy")
        st.caption(f"Pearson r = {pairs.fedfunds.corr(pairs[x]):.3f} · {len(pairs)} paired months · {transformation}")
    else:
        st.info("At least three paired observations with variation are needed for a correlation.")
    st.warning(CAUSAL_NOTE)
    download = view[[*selected, "black_white_gap_pp", "fedfunds", *RACE_STATUS_COLUMNS, "fedfunds_status"]]
    st.download_button("Download selected period · CSV", download.to_csv(index_label="date").encode(), file_name=f"race_unemployment_{start:%Y%m}_{end:%Y%m}.csv", mime="text/csv", key="race_download")
    st.dataframe(download, use_container_width=True)
    st.caption("Source-missing and unreleased values remain null. October 2025 is source-missing in the four unemployment series. FEDFUNDS is the monthly average effective rate and is not seasonally adjusted.")
    with st.expander("Definitions and sources"):
        st.markdown(CATEGORY_NOTE)
        for sid, col in RACE_SERIES.items():
            st.markdown(f"- [{GROUP_LABELS[col]} · {sid}](https://fred.stlouisfed.org/series/{sid}): percent, monthly, seasonally adjusted; BLS Current Population Survey.")
        st.markdown("[BLS demographic definitions](https://www.bls.gov/cps/definitions.htm#hispanic) · [Federal funds rate](https://fred.stlouisfed.org/series/FEDFUNDS)")
        st.caption("Sampling error and differences in group composition matter. These series do not supply an individual-level explanation or uncertainty intervals for estimated differences.")
