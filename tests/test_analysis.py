from macro_pipeline.analysis import write_analysis, lag_correlations
from macro_pipeline.pipeline import run_pipeline
from macro_pipeline.db import read_dataset


def test_analysis_outputs_and_lag_sample_sizes(settings, client, tmp_path):
    run_pipeline(settings, client)
    frame, run = read_dataset(settings.db_path)
    result = write_analysis(frame, run, tmp_path / "reports")
    assert len(result["findings"]) >= 7
    assert (tmp_path / "reports/figures/correlations.png").stat().st_size > 1000
    lag = lag_correlations(frame)
    assert lag.loc[lag.outcome == "unrate", "n"].iloc[0] - lag.loc[lag.outcome == "unrate", "n"].iloc[-1] == 24
