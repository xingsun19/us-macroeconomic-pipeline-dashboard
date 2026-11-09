"""Descriptive race/ethnicity analysis with explicit windows and paired samples."""

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .db import RACE_COLUMNS
from .demographics import GROUP_LABELS, GROUP_COLORS, CATEGORY_NOTE, CAUSAL_NOTE

CRISIS_WINDOWS = (
    ("Financial crisis and aftermath (2008–2010)", "2007-12-01", "2008-01-01", "2010-12-01"),
    ("Pandemic shock and aftermath (2020–2021)", "2020-02-01", "2020-03-01", "2021-12-01"),
)
RACE_REPORT_FILES = (
    "race/monthly_unemployment.csv", "race/descriptive_statistics.csv", "race/annual_summary.csv",
    "race/crisis_comparison.csv", "race/policy_correlations.csv", "race/analysis_summary.json", "race/findings.md",
    "race/figures/trends.png", "race/figures/black_white_gap.png",
    "race/figures/crisis_comparison.png", "race/figures/policy_relationships.png",
)


def crisis_comparison(frame):
    rows = []
    for label, baseline, start, end in CRISIS_WINDOWS:
        for group in RACE_COLUMNS:
            series = frame.loc[start:end, group].dropna()
            base = frame[group].get(pd.Timestamp(baseline), np.nan)
            rows.append({"window": label, "group": group, "baseline_month": baseline[:7], "baseline_rate": base,
                         "peak_month": series.idxmax().strftime("%Y-%m") if len(series) else None,
                         "peak_rate": series.max(), "peak_change_pp": series.max() - base,
                         "last_observed_month": series.index[-1].strftime("%Y-%m") if len(series) else None,
                         "last_rate": series.iloc[-1] if len(series) else np.nan, "observed_months": len(series)})
    return pd.DataFrame(rows)


def policy_correlations(frame):
    """Compute changes and lags on the full monthly grid before dropping nulls."""
    rows = []
    for transformation in ("Levels", "Monthly changes"):
        source = frame if transformation == "Levels" else frame.select_dtypes(include="number").diff()
        for lag in (0, 6, 12):
            for group in [*RACE_COLUMNS, "black_white_gap_pp"]:
                pair = pd.concat([source.fedfunds.rename("rate"), source[group].shift(-lag).rename("outcome")], axis=1).dropna()
                valid = len(pair) >= 3 and pair.rate.nunique() > 1 and pair.outcome.nunique() > 1
                rows.append({"transformation": transformation, "outcome": group, "lag_months": lag,
                             "pearson_r": pair.rate.corr(pair.outcome) if valid else np.nan, "paired_months": len(pair)})
    return pd.DataFrame(rows)


def annual_summary(frame):
    rows = []
    for year, part in frame.groupby(frame.index.year):
        for group in [*RACE_COLUMNS, "black_white_gap_pp"]:
            observed = part[group].dropna()
            rows.append({"year": year, "indicator": group, "mean": observed.mean(), "observed_months": len(observed)})
    return pd.DataFrame(rows)


def race_findings(frame, run):
    gap = frame.black_white_gap_pp.dropna()
    text = [f"The {run['as_of']} FRED vintage contains {len(frame)} monthly rows from {frame.index.min():%B %Y} to {frame.index.max():%B %Y}. All four unemployment series are seasonally adjusted percentages."]
    for group in RACE_COLUMNS:
        observed = frame[group].dropna()
        text.append(f"{GROUP_LABELS[group]} unemployment is {observed.iloc[-1]:.1f}% in {observed.index[-1]:%B %Y}; its sample mean is {observed.mean():.2f}% across {len(observed)} observed months.")
    text.append(f"The Black–White gap averages {gap.mean():.2f} percentage points across {len(gap)} paired months. It is {gap.iloc[-1]:.2f} pp in {gap.index[-1]:%B %Y}, compared with {gap.iloc[0]:.2f} pp in {gap.index[0]:%B %Y}; its sample maximum is {gap.max():.2f} pp in {gap.idxmax():%B %Y}.")
    crisis = crisis_comparison(frame)
    for window, part in crisis.groupby("window", sort=False):
        available = part.dropna(subset=["peak_change_pp"])
        if not available.empty:
            row = available.loc[available.peak_change_pp.idxmax()]
            text.append(f"Within the {window} comparison window, {GROUP_LABELS[row['group']]} has the largest measured baseline-to-peak increase among these four series: {row.peak_change_pp:.1f} pp, from {row.baseline_rate:.1f}% in {row.baseline_month} to {row.peak_rate:.1f}% in {row.peak_month}. This is an event-window description, not an estimate of the event's causal effect.")
    policy = policy_correlations(frame)
    for transform in ("Levels", "Monthly changes"):
        row = policy.loc[(policy.transformation == transform) & (policy.outcome == "black_white_gap_pp") & (policy.lag_months == 0)].iloc[0]
        coefficient = f"{row.pearson_r:.3f}" if pd.notna(row.pearson_r) else "unavailable (insufficient variation or pairs)"
        text.append(f"The contemporaneous federal-funds/Black–White-gap correlation in {transform.lower()} is {coefficient}, using {row.paired_months} paired months. The policy rate responds to economic conditions, so these associations do not identify policy effects.")
    return text


def make_race_figures(frame, folder, crisis, policy):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .2, "figure.facecolor": "#fafbf9", "axes.facecolor": "#fafbf9"})
    fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
    for group in RACE_COLUMNS:
        ax.plot(frame.index, frame[group], label=GROUP_LABELS[group], color=GROUP_COLORS[group], lw=1.8)
    ax.set(title="Unemployment by race and ethnicity", ylabel="Seasonally adjusted unemployment rate (%)")
    ax.legend(frameon=False, ncol=2)
    fig.savefig(folder / "trends.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
    ax.plot(frame.index, frame.black_white_gap_pp, color=GROUP_COLORS["black"], lw=1.8)
    ax.axhline(0, color="#142c3a", lw=.8)
    ax.set(title="Black–White unemployment gap", ylabel="Black rate minus White rate (percentage points)")
    fig.savefig(folder / "black_white_gap.png", dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, (window, part) in zip(axes, crisis.groupby("window", sort=False)):
        ax.bar(part.group, part.peak_change_pp, color=[GROUP_COLORS[g] for g in part.group])
        ax.set(title=window.replace(" and aftermath", "\nand aftermath"), ylabel="Increase from baseline to window peak (pp)")
        ax.set_xticks(range(4), ["White", "Black", "Asian", "Hispanic/Latino"])
    fig.savefig(folder / "crisis_comparison.png", dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    labels = {**GROUP_LABELS, "black_white_gap_pp": "Black–White gap"}
    for ax, transform in zip(axes, ("Levels", "Monthly changes")):
        part = policy.loc[(policy.transformation == transform) & (policy.lag_months == 0)]
        ax.barh([labels[g] for g in part.outcome], part.pearson_r, color="#167d9a")
        ax.axvline(0, color="#142c3a", lw=.8)
        ax.set(xlim=(-1, 1), xlabel="Paired Pearson correlation with federal funds", title=transform)
    fig.savefig(folder / "policy_relationships.png", dpi=160); plt.close(fig)


def write_race_analysis(frame, run, reports_dir):
    folder = Path(reports_dir) / "race"
    folder.mkdir(parents=True, exist_ok=True)
    crisis, policy = crisis_comparison(frame), policy_correlations(frame)
    frame.to_csv(folder / "monthly_unemployment.csv", index_label="date")
    frame[[*RACE_COLUMNS, "black_white_gap_pp", "fedfunds"]].describe().T.to_csv(folder / "descriptive_statistics.csv")
    annual_summary(frame).to_csv(folder / "annual_summary.csv", index=False)
    crisis.to_csv(folder / "crisis_comparison.csv", index=False)
    policy.to_csv(folder / "policy_correlations.csv", index=False)
    make_race_figures(frame, folder / "figures", crisis, policy)
    text = race_findings(frame, run)
    summary = {"run_id": run["run_id"], "as_of": run["as_of"], "rows": len(frame), "findings": text,
               "category_note": CATEGORY_NOTE, "interpretation_note": CAUSAL_NOTE}
    (folder / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (folder / "findings.md").write_text(
        "# Unemployment by Race & Ethnicity\n\n" + "\n\n".join(text) + "\n\n## Interpretation and methods\n\n" + CATEGORY_NOTE + "\n\n" + CAUSAL_NOTE
        + "\n\nFinancial-crisis comparisons use December 2007 as baseline and January 2008–December 2010 for the peak search. Pandemic comparisons use February 2020 as baseline and March 2020–December 2021 for the peak search. These are stated analysis windows, not official recession dates. Annual means use available months; counts disclose partial years. Gaps require both groups in the same month. No values are imputed. Lagged correlations pair the rate at t with unemployment/gap at t+k on the complete monthly grid. They are exploratory, with no causal identification or multiple-testing-adjusted inference. CPS estimates have sampling error; the four series alone do not provide confidence intervals.\n\n## Sources\n\n"
        + "- [BLS definitions: race and Hispanic ethnicity](https://www.bls.gov/cps/definitions.htm#hispanic)\n"
        + "- [White](https://fred.stlouisfed.org/series/LNS14000003), [Black](https://fred.stlouisfed.org/series/LNS14000006), [Asian](https://fred.stlouisfed.org/series/LNS14032183), [Hispanic or Latino](https://fred.stlouisfed.org/series/LNS14000009), and [federal funds](https://fred.stlouisfed.org/series/FEDFUNDS), via FRED.\n")
    return summary
