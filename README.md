# besFundLens

**English-first, bilingual-ready analytics engine for Turkish pension funds.**

besFundLens decomposes pension fund AUM movements into **market effect** and **estimated investor flow**, maps portfolio DNA, classifies funds by their asset allocation, identifies market-flow regimes, and generates bilingual Markdown reports.

> The project currently focuses on Turkish BES / pension fund data. It is designed as a reusable analytics engine rather than a price-prediction model.

## Why this project exists

Most fund analysis stops at return and AUM change. besFundLens asks a deeper question:

> Did AUM change because markets moved, or because investors added/withdrew money?

It combines:

- Fund DNA / portfolio allocation analysis
- Market-scope and currency exposure mapping
- AUM change decomposition
- Estimated net investor flow
- Participant change analysis
- Model-driven allocation classification (v2)
- Market-flow quadrant analysis
- English and Turkish narrative reporting

## What's new in v0.2.0

**Allocation classification.** Funds are grouped by what they actually hold, by a
clustering model over their allocation vectors — not by a hand-written rule
chain. See [docs/CLASSIFICATION.md](docs/CLASSIFICATION.md).

- Classes are **discovered** by KMeans over window-averaged allocation vectors;
  `k` is chosen by silhouette score. A rule-based taxonomy only *names* each
  discovered class from its centroid.
- Classification runs over the **whole lookback window**, not a single day, and
  reports class stability, style drift and allocation volatility.
- Four configurable categorical axes sit alongside the asset class:
  **participation** (interest-free), **risk band**, **currency band** and
  **look-through band**.
- Every verdict carries a **confidence score**, discounted by how much of the
  portfolio is held in other funds and therefore not visible.
- The fitted model saves to JSON and can be **reused across periods**, so class
  names stay comparable between reports.

The v0.1 rule-based `archetype` column is unchanged and still populated.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

## Quick start with SQLite cache

SQLite is optional but recommended for multi-year analysis and repeated workflows.

```bash
python scripts/fetch_history.py \
  --start 2021-06-15 \
  --end 2026-06-15 \
  --db-path data/besfundlens.sqlite
```

Generate an English report:

```bash
python scripts/generate_report.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --language en \
  --output sample_reports/market_report_en.md
```

Generate a Turkish report:

```bash
python scripts/generate_report.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --language tr \
  --output sample_reports/market_report_tr.md
```

## Python API

```python
from besfundlens.workflows import run_universe_analysis_from_sqlite

result = run_universe_analysis_from_sqlite(
    db_path="data/besfundlens.sqlite",
    lookback="1m",
    language="en",
    top_n=10,
)

print(result["markdown"])
```

Selected fund comparison:

```python
from besfundlens.workflows import compare_funds_from_sqlite
from besfundlens.core.engine import selected_funds_report_to_markdown

comparison = compare_funds_from_sqlite(
    db_path="data/besfundlens.sqlite",
    fund_codes=["AAJ", "MHD", "MEA"],
    lookback="1m",
    sort_by="market_effect_pct",
    ascending=False,
)

print(selected_funds_report_to_markdown(comparison, language="en"))
print(selected_funds_report_to_markdown(comparison, language="tr"))
```

## Allocation classification

Classify the universe and fit a model:

```bash
python scripts/classify_funds.py \
  --db-path data/besfundlens.sqlite \
  --lookback 3m \
  --fit \
  --model-path models/allocation_classifier.json \
  --output reports/classification.md \
  --language en
```

Reuse that model on a different window, so the class names mean the same thing:

```bash
python scripts/classify_funds.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --predict \
  --model-path models/allocation_classifier.json \
  --output reports/classification_1m.csv
```

From Python:

```python
from besfundlens import classify_funds_from_sqlite

result = classify_funds_from_sqlite(
    db_path="data/besfundlens.sqlite",
    lookback="3m",
    save_model_to="models/allocation_classifier.json",
)

df = result["classification_df"]
print(df[[
    "fonKodu", "asset_class", "asset_class_family", "class_confidence",
    "risk_band", "currency_band", "participation_class", "style_drift",
]].head())
```

Every threshold is configurable:

```python
from besfundlens import ClassificationConfig, classify_funds_from_sqlite

config = ClassificationConfig(
    feature_space="detailed",       # broad | detailed | raw
    k_range=(6, 20),                # silhouette-selected within this range
    risk_band_method="quantile",    # fixed | quantile | kmeans1d
    risk_band_edges=(5.0, 25.0, 55.0),
    currency_band_threshold=50.0,
    lookthrough_penalty=True,
)

result = classify_funds_from_sqlite(db_path="data/besfundlens.sqlite", config=config)
```

Classification is merged into the market narrative report automatically. Pass
`classify=False` to `run_universe_analysis()` to skip it.

## Lookback presets

| Preset | Meaning |
|---|---:|
| `1m` | 20 available fund intervals |
| `3m` | 60 available fund intervals |
| `6m` | 120 available fund intervals |
| `1y` | 240 available fund intervals |

The project uses **available observations / intervals**, not calendar days. This is important because fund data may skip weekends, public holidays, or missing publication dates.

## Data ingestion strategy

besFundLens supports two workflows:

1. **Direct API mode** for quick experiments and notebooks.
2. **SQLite cache mode** for multi-year analysis and repeated reporting.

The cache updater uses a period replacement approach: it removes records from the update start date onward and appends freshly fetched data. This is intentional because financial fund data may receive late corrections.

## Repository structure

```text
besfundlens/
  core/            # analytics engine, asset metadata, shared utilities
  classification/  # v2 allocation classification layer
  data/            # API client and loaders
  storage/         # SQLite cache utilities
  reports/         # markdown report helpers
scripts/           # CLI-style scripts
examples/          # small demos
docs/              # methodology notes
sample_reports/
tests/
```

## Responsible data use

This project relies on publicly accessible fund data endpoints used in the original research scripts. Please use the fetch utilities responsibly, avoid excessive API requests, and prefer SQLite caching for repeated analysis.

## Acknowledgements

This project was developed by **İlyas Hakyemez** with AI-assisted coding, refactoring, and documentation support from ChatGPT.

The project idea, financial domain logic, data validation, testing, interpretation framework, and product direction were defined and reviewed by the author. AI assistance was used as a development support tool for code structuring, modularization, bilingual reporting, and repository preparation.

## Disclaimer

This project is for research, education, and analytics prototyping. It is not investment advice.
