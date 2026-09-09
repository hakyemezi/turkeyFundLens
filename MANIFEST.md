# besFundLens Repository Manifest

Generated package: `besfundlens` (v0.2.0).

## Included

- Import-safe analytics engine (`besfundlens/core/engine.py`)
- Shared utilities (`besfundlens/core/utils.py`)
- Asset metadata and Fund DNA aggregation (`besfundlens/core/asset_metadata.py`)
- Allocation classification layer (`besfundlens/classification/`)
  - `config.py` — all tunable thresholds
  - `features.py` — window-averaged allocation matrix and sub-window slices
  - `taxonomy.py` — centroid to human-readable class name (EN/TR)
  - `model.py` — `AllocationClassifier` (fit / predict / save / load)
  - `axes.py` — participation, risk, currency and look-through axes
  - `stability.py` — class stability, style drift, allocation volatility
  - `pipeline.py` — `classify_universe()` orchestration
  - `report.py` — bilingual Markdown sections
- TEFAS/Fonturkey data client (`besfundlens/data/tefas_client.py`)
- Optional SQLite cache layer (`besfundlens/storage/sqlite_store.py`)
- Streamlit web interface (`streamlit_app.py`, `app_translations.py`), fetching
  live from TEFAS with the SQLite cache as the alternative source
- `load_turkeyfundsdata_frame()` for frames from the turkeyfundsdata repository
- Workflow helpers (`besfundlens/workflows.py`)
- English and Turkish sample reports
- CLI scripts for fetching, updating, generating reports, comparing and classifying funds
- Classification methodology notes (`docs/CLASSIFICATION.md`)
- Smoke tests including a synthetic in-memory dataset and a synthetic classification universe

## Validation performed

- Python compile check for all `.py` files
- Duplicate function definition check per file
- Import-safe package test without local DB
- Pytest suite (58 tests): imports, localization, lookback, the AUM decomposition
  arithmetic on constructed cases where the answer is known, label translations
  checked against the values the engine can actually emit, the turkeyfundsdata
  loader, a synthetic analytics smoke test, and the classification suite (model
  recovery, k selection, model persistence round-trip, stability and drift,
  secondary axes, taxonomy naming, engine integration, bilingual reporting,
  config validation)
- Live-data validation on a 399-fund BES universe:
  - the participation axis was cross-checked against fund names — 120 of the 121
    funds named "katılım" are detected, and the one exception is a fund-of-funds
    whose portfolio is not visible enough to support a verdict
  - the sample reports in `sample_reports/` are generated from this run

## Notes

The package does not include a SQLite database. Users can fetch/cache data with
the provided scripts or load their own compatible DataFrames.

Fitted classification models are written to `models/` and report output to
`reports/`; both are gitignored.

## Backward compatibility in v0.2.0

`besfundlens/core/engine.py` no longer defines the generic helpers or the asset
metadata maps — they moved to `core/utils.py` and `core/asset_metadata.py`. The
engine re-exports every moved name, so imports such as
`from besfundlens.core.engine import safe_divide` continue to work.

The v0.1 rule-based `classify_fund_archetype()` and the `archetype` column are
unchanged.
