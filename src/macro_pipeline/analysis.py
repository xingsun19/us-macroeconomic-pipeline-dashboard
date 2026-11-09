"""Reproducible descriptive analysis; associations are not causal estimates."""

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LABELS = {
    "unrate": "Unemployment rate (%)", "cpiaucsl": "CPI (1982–84 = 100)",
    "fedfunds": "Federal funds rate (%)", "cpi_yoy": "CPI inflation (YoY, %)",
    "cpi_mom": "CPI inflation (MoM, %)", "unrate_change_pp": "Unemployment change (pp)",
    "fedfunds_change_pp": "Federal funds change (pp)", "real_rate_proxy": "Ex-post real-rate proxy (pp)",
}
COLORS = ["#008c95", "#e09637", "#5466b3"]
ECONOMIC_COLUMNS = ["unrate", "cpi_yoy", "fedfunds"]


def lag_correlations(frame, max_lag=24):
    """Positive lag k pairs the rate at t with the outcome at t+k."""
    rows = []
    for outcome in ("cpi_yoy", "unrate"):
        for lag in range(max_lag + 1):
            pair = pd.concat([frame.fedfunds.rename("rate"), frame[outcome].shift(-lag).rename("outcome")], axis=1).dropna()
            rows.append({"outcome": outcome, "lag_months": lag, "pearson_r": pair.rate.corr(pair.outcome) if len(pair) > 2 else np.nan, "n": len(pair)})
    return pd.DataFrame(rows)


def findings(frame, run):
    un = frame.unrate.dropna()
    cpi = frame.cpiaucsl.dropna()
    inflation = frame.cpi_yoy.dropna()
    rates = frame.fedfunds.dropna()
    pair = frame[["unrate", "cpi_yoy"]].dropna()
    complete = frame[ECONOMIC_COLUMNS].dropna()
    level_r = pair.unrate.corr(pair.cpi_yoy)
    change_r = frame.unrate.diff().corr(frame.cpi_yoy.diff())
    return [
        f"The validated snapshot spans {frame.index.min():%B %Y}–{frame.index.max():%B %Y} ({len(frame)} monthly rows), using the FRED vintage dated {run['as_of']}.",
        f"Unemployment peaked at {un.max():.1f}% in {un.idxmax():%B %Y}; its latest available value is {un.iloc[-1]:.1f}% ({un.index[-1]:%B %Y}). The peak identifies the largest labor-market disruption in this sample; three series alone cannot identify its causes.",
        f"CPI increased {100 * (cpi.iloc[-1] / cpi.iloc[0] - 1):.1f}% between {cpi.index[0]:%B %Y} and {cpi.index[-1]:%B %Y}. The price level and the inflation rate answer different questions: lower positive inflation still means rising prices.",
        f"Year-over-year inflation calculated from seasonally adjusted CPI peaked at {inflation.max():.2f}% in {inflation.idxmax():%B %Y}; the latest available reading is {inflation.iloc[-1]:.2f}% ({inflation.index[-1]:%B %Y}). It can differ from the headline unadjusted CPI inflation rate.",
        f"The federal funds rate is {rates.iloc[-1]:.2f}% in {rates.index[-1]:%B %Y}, versus a sample maximum of {rates.max():.2f}% in {rates.idxmax():%B %Y}. Its monthly frequency smooths changes within a month.",
        f"The unemployment–inflation Pearson correlation is {level_r:.3f} across {len(pair)} paired months; the correlation of monthly changes is {change_r:.3f}. This sensitivity to transformation cautions against treating a full-sample correlation as a stable Phillips-curve relationship.",
        f"The latest common observation across unemployment, inflation, and the policy rate is {complete.index[-1]:%B %Y}. The ex-post real-rate proxy is {complete.fedfunds.iloc[-1] - complete.cpi_yoy.iloc[-1]:.2f} percentage points. It uses realized past inflation, not expected future inflation or a structural neutral rate.",
    ]


def make_figures(frame, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "#fafbf9", "axes.facecolor": "#fafbf9", "axes.grid": True, "grid.alpha": 0.2})
    paths = []
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    for ax, col, color in zip(axes, ["unrate", "cpiaucsl", "fedfunds"], COLORS):
        ax.plot(frame.index, frame[col], color=color, lw=1.8)
        ax.set_ylabel(LABELS[col])
    axes[0].set_title("Three views of the U.S. economy", loc="left")
    fig.savefig(output / "historical_trends.png", dpi=160)
    paths.append("historical_trends.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
    for col, color in zip(["cpi_yoy", "fedfunds", "real_rate_proxy"], COLORS):
        ax.plot(frame.index, frame[col], label=LABELS[col], color=color)
    ax.axhline(0, color="#182c39", lw=.7)
    ax.set_title("Inflation, monetary policy, and the ex-post real-rate proxy", loc="left")
    ax.set_ylabel("Percent / percentage points")
    ax.legend(frameon=False)
    fig.savefig(output / "inflation_and_policy.png", dpi=160)
    paths.append("inflation_and_policy.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, data, title in zip(axes, [frame[ECONOMIC_COLUMNS], frame[ECONOMIC_COLUMNS].diff()], ["Levels", "Monthly changes"]):
        corr = data.corr()
        ax.imshow(corr, vmin=-1, vmax=1, cmap="BrBG")
        ax.set_xticks(range(3), ["Unemployment", "Inflation", "Fed funds"])
        ax.set_yticks(range(3), ["Unemployment", "Inflation", "Fed funds"])
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{corr.iloc[i,j]:.2f}", ha="center", va="center", color="white" if abs(corr.iloc[i,j]) > .6 else "#132a36")
        ax.set_title(f"Pearson correlation · {title}")
        ax.grid(False)
    fig.savefig(output / "correlations.png", dpi=160)
    paths.append("correlations.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    pair = frame[["unrate", "cpi_yoy"]].dropna()
    points = axes[0].scatter(pair.unrate, pair.cpi_yoy, c=pair.index.year, cmap="viridis", s=17, alpha=.75)
    axes[0].set(xlabel=LABELS["unrate"], ylabel=LABELS["cpi_yoy"], title="Unemployment and inflation")
    fig.colorbar(points, ax=axes[0], label="Year")
    rolling = frame.unrate.rolling(60, min_periods=60).corr(frame.cpi_yoy)
    axes[1].plot(frame.index, rolling, color=COLORS[0])
    axes[1].axhline(0, lw=.7, color="#182c39")
    axes[1].set(title="Relationship stability", ylabel="60-month rolling Pearson correlation", ylim=(-1, 1))
    fig.savefig(output / "relationship_stability.png", dpi=160)
    paths.append("relationship_stability.png")
    plt.close(fig)
    return paths


def write_analysis(frame, run, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    figures = make_figures(frame, output / "figures")
    frame.to_csv(output / "monthly_indicators.csv", index_label="date")
    frame[list(LABELS)].describe().T.to_csv(output / "descriptive_statistics.csv")
    frame[ECONOMIC_COLUMNS].corr().to_csv(output / "correlation_levels.csv")
    frame[ECONOMIC_COLUMNS].diff().corr().to_csv(output / "correlation_changes.csv")
    lag_correlations(frame).to_csv(output / "lag_correlations.csv", index=False)
    text = findings(frame, run)
    summary = {"as_of": run["as_of"], "run_id": run["run_id"], "rows": len(frame), "findings": text, "figures": figures}
    (output / "analysis_summary.json").write_text(json.dumps(summary, indent=2))
    # An explicit user request for an English project report; kept with repository documentation.
    (output / "findings.md").write_text("# Empirical findings\n\n" + "\n\n".join(text) + "\n\n## Interpretation limits\n\nThese are descriptive associations, not causal estimates or forecasts. Monthly observations are autocorrelated; level correlations may reflect trends, policy endogeneity, and structural breaks. Lag searches are exploratory and involve multiple comparisons. No p-values or causal claims are inferred. FRED may revise historical values. Data are a current-vintage snapshot, not a real-time backtest. Missing/unreleased months are not imputed.\n\n## Sources\n\n- [BLS unemployment via FRED](https://fred.stlouisfed.org/series/UNRATE)\n- [BLS seasonally adjusted CPI via FRED](https://fred.stlouisfed.org/series/CPIAUCSL)\n- [Federal Reserve effective federal funds rate via FRED](https://fred.stlouisfed.org/series/FEDFUNDS)\n")
    return summary
