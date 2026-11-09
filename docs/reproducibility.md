# Reproducing and preserving the analysis

## Included real-data archive

`snapshots/fred-2026-11-09.json` is the original raw response bundle from a successful FRED ingestion, including all seven series, metadata, observation dates, values, vintage fields, and the 1999 macroeconomic warm-up year. It is real source data, distinct from the synthetic unit-test fixtures. `snapshots/manifest.json` records its SHA-256, vintage, source links, capture run, retrieval time, observation counts, and published coverage. No API key, request URL containing credentials, or local database path is included.

The default archived vintage produces 322 macroeconomic rows (January 2000–October 2026) and 286 race/ethnicity rows (January 2003–October 2026). The original three-series archive remains available through `snapshots/manifest-macro-2026-11-08.json`. It preserves official missing observations. Validation uses the archived vintage date, so the snapshot does not fail freshness checks simply because the calendar has advanced.

## Offline replay

Prepare once with internet access:

```bash
bash scripts/run.sh --prepare-offline
```

Then reproduce without a FRED key or FRED access:

```bash
bash scripts/run.sh --offline
```

The replay container has `network_mode: none`, pulls no images, and receives no API credential. It checks the archive hash and metadata, rebuilds SQLite using the same ingestion/cleaning/validation/publication functions, executes all notebook cells, and exports HTML, charts, findings, and tables. The dashboard uses that database and labels the archived vintage. Add `--batch` to stop after generating the report.

| Output | Offline location |
|---|---|
| Rebuilt database and raw replay audit | `data/offline/` |
| HTML report | `reports/offline/eda.html` |
| Executed notebook | `reports/offline/01_macroeconomic_eda.ipynb` |
| Charts, statistics, data, and findings | `reports/offline/`, including the `race/` subdirectory |
| Archive provenance and report hashes | `reports/offline/snapshot_provenance.json`, `reports/offline/report_manifest.json` |

Live files remain in `data/macroeconomics.db`, `reports/`, and `notebooks/`. Offline outputs do not overwrite them. The snapshot demonstrates historical reproducibility; it does not provide future observations.

## Preserve the runtime for five years

Pinned packages and image digests identify dependencies, but do not ensure registries remain available. Keep the repository, raw snapshot, and a prepared image together in durable storage. After preparing the runtime:

```bash
mkdir -p archives
docker save -o archives/us-macro-app.tar us-macro-app:1.0.0
shasum -a 256 archives/us-macro-app.tar > archives/us-macro-app.tar.sha256
```

Store the archive outside the working laptop as well. On the same CPU architecture, restore it with `docker load -i archives/us-macro-app.tar`, then run `bash scripts/run.sh --offline`. Save a separate built image for each target architecture (for example ARM64 and AMD64); an image saved on Apple Silicon is not a portable replacement for every Windows/Linux machine. Docker itself must also remain available and compatible. The snapshot alone cannot preserve the operating system or container runtime.

After code changes, prepare the image again before running offline so the cached image includes the revised code. For an already-installed native Python environment, `python scripts/run_offline.py` regenerates the offline artifacts without Docker or network requests.
