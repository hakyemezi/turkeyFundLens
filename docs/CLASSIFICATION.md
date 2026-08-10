# Allocation Classification (v2)

How besFundLens classifies pension funds by what they actually hold.

## Design principle

The model decides the grouping; the taxonomy only names it.

Version 0.1 classified funds with a hand-written `if/elif` chain
(`classify_fund_archetype`). That chain is order-dependent, uses thresholds
baked into the function body, sees only one day of data, and produces no measure
of how confident the verdict is. It is still available and still populates the
`archetype` column, but v2 replaces it as the primary axis.

In v2:

1. Each fund's allocation vectors inside the lookback window are averaged.
2. A clustering model groups funds by that vector. `k` is chosen automatically.
3. A rule-based taxonomy reads each **cluster centroid** and produces a
   human-readable name for the group.

The rules never look at an individual fund. They look at the centroid of a group
the model discovered. This is what "the model classifies, the taxonomy names"
means in practice, and it is why the classes reflect the shape of the actual
universe rather than a fixed list someone wrote down in advance.

## Pipeline

```
panel (raw allocation columns)
  -> window selection        last N observations per fund, quality-filtered
  -> aggregation             raw instrument codes -> feature space
  -> renormalisation         each row rescaled to sum to 100
  -> KMeans                  k selected by silhouette score
  -> taxonomy                centroid -> class name (EN/TR) + level-1 family
  -> confidence              margin to runner-up, discounted by look-through
  -> secondary axes          participation / risk / currency / look-through
  -> stability               sub-window class stability, drift, volatility
```

Entry point: `besfundlens.classification.classify_universe()`.

## Feature space

`ClassificationConfig.feature_space` selects what the model sees:

| Value | Aggregation | Dimensions |
|---|---|---:|
| `broad` (default) | `broad_asset_group` | ~15 |
| `detailed` | `asset_group` | ~35 |
| `raw` | none — one feature per instrument code | ~54 |

`broad` is the default because its centroids are directly readable ("Fixed
Income 62%, Equity 21%") and because the coarser space is less sensitive to a
fund shuffling between two near-identical instruments.

Rows are renormalised to sum to 100 (`renormalize=True`). TEFAS distribution
totals drift between roughly 90 and 105; without renormalisation, part of the
distance between two funds would just be that drift.

`transform="hellinger"` applies an element-wise square root before clustering.
It spreads out funds that differ only in small allocations, at the cost of
centroids no longer reading as percentages. Off by default.

## Choosing k

Unless `config.k` is set, the model fits KMeans for every `k` in
`config.k_range` (default 4–16) and keeps the one with the highest silhouette
score. The selected `k`, the winning score and every candidate score are
recorded in the model artifact.

Determinism comes from a fixed `random_state` (default 42) and `n_init=10`.

**The silhouette curve is flat on real data — plan for it.** Fund allocations
form a continuum rather than well-separated blobs, so silhouette barely
discriminates between candidate `k` values. On a 399-fund BES universe over a
3-month window, the whole 4–16 range scored between 0.45 and 0.52, and `k=5`
won by roughly 0.02 over `k=7`:

| k | 4 | 5 | 6 | 7 | 8 | 9 | 10 | … | 16 |
|---|---|---|---|---|---|---|---|---|---|
| silhouette | 0.478 | **0.523** | 0.496 | 0.506 | 0.501 | 0.504 | 0.454 | … | 0.484 |

The five classes it picked are coherent (equity, fixed income, lease
certificates, precious metals, fund-of-funds), but a margin that thin is not a
strong claim that five is the right number. Treat the automatic choice as a
sensible default, not an answer:

- Set `config.k` (or `--k`) when you want a specific granularity.
- Switch to `feature_space="detailed"` for a finer taxonomy. On the same
  universe with `--feature-space detailed --k 10` the classes separate
  domestic from FX government fixed income, and public from private sector
  lease certificates — distinctions the broad space cannot express, because
  both sides map to the same broad group.

A silhouette around 0.5 on real data is normal and is reported honestly in the
"Classification Quality" section rather than hidden.

**Fallback.** When the universe has fewer than `min_funds_for_model` funds
(default 40), clustering is skipped: each fund is named directly from its own
allocation vector, and funds sharing a name are collapsed into one class whose
centroid is their mean. This is pure rule-based classification and is what runs
on small or synthetic datasets. `fit_info.model_fitted` is `False` and
`fit_info.fallback_reason` explains why.

## Naming a centroid

Given a centroid and the thresholds in the config:

| Condition | Name |
|---|---|
| top weight ≥ `dominant_threshold` (60) | `Equity Weighted` |
| top weight ≥ `primary_threshold` (40) | `Equity Tilted Multi-Asset` |
| otherwise | `Multi-Asset (Equity / Fixed Income)` |

Ties fall back to feature order, so a name never depends on sort implementation
details. Two clusters that reduce to the same name are disambiguated by their
second-largest group — a report with duplicate row labels is unreadable.

Each class also gets a **level-1 family**: Equity, Fixed Income, Money Market,
Precious Metals, Fund of Funds, Alternative, Multi-Asset or Other.

Because the name is a pure function of the centroid, a class keeps its name for
as long as its composition is stable.

## Confidence

```
confidence = (1 - d₁/d₂) × (100 - lookthrough_weight)/100
```

where `d₁` and `d₂` are the distances to the nearest and second-nearest
centroid. 1.0 means the fund sits on its centroid; 0.0 means it is equidistant
between two classes and the assignment is effectively a coin flip.

The look-through discount is the honest part. A fund holding 40% of other funds
may sit neatly on a centroid, but we cannot see what those funds hold — the
label is only as trustworthy as the share of the portfolio that is visible. Set
`lookthrough_penalty=False` to get the raw margin.

`runner_up_class` names the second-nearest class, so a low-confidence verdict
comes with its alternative attached.

## Stability and drift

The window is split into `sub_window_count` slices (default 4), sliced by each
fund's own available observations rather than by calendar dates it may be
missing.

| Metric | Meaning |
|---|---|
| `class_stability` | share of sub-windows the fund stayed in its modal class (0–1) |
| `allocation_volatility` | mean L1 distance between consecutive sub-windows |
| `style_drift` | L1 distance between the first and last sub-window |
| `drift_flag` | the latest snapshot lands in a different class than the window |

L1 distances are in percentage points and count moves on both sides: shifting
10 points from equity into bonds registers as 20.

A fund with high `style_drift` and low `class_stability` changed its allocation
during the window. Its class label describes an average that it may no longer
hold.

**Missing sub-windows propagate as NaN, not zero.** A fund that launched
mid-window has no earlier allocation to compare against. Filling those
sub-windows with zeros would score it as having rotated its entire portfolio and
put it at the top of the drift watchlist without it ever changing a holding, so
such funds get `style_drift = NaN` and are still classified normally.

## Secondary axes

Four categorical columns sit next to the asset class, each with a `_tr` variant.
They are threshold-based rather than model-derived, because each encodes a
*definition* rather than a pattern to be discovered.

### `participation_class` — Participation / Conventional / Mixed

| Verdict | Condition |
|---|---|
| Participation | interest-bearing weight ≤ `participation_tolerance` (1%) **and** recognised participation-compatible weight ≥ `participation_min_coverage` (60%) |
| Mixed | no interest-bearing exposure, but too much of the portfolio sits in instruments we cannot vouch for either way |
| Conventional | interest-bearing instruments above tolerance |

No unsupervised method can recover "interest-free" from allocation data — it is
a constraint on which instruments a fund may hold, not a pattern in the numbers.
The instrument sets are `INTEREST_BEARING_CODES` and `PARTICIPATION_CODES`, both
overridable through the config.

**`btaa` / `btas` count as participation-compatible, not as repo.** The BIST
Taahhütlü İşlemler Pazarı is a sale-with-repurchase-commitment structure created
as the participation-compatible route to short-term liquidity. Two thirds of the
funds named "katılım" in the live BES universe hold it. Filing it with repo
mislabels most of them: on a 399-fund universe it dropped detection from 120 of
121 declared participation funds down to 50.

**Negative legs are collateral, and only the interest screen uses magnitude.**
A negative weight (a fund reporting −8% repo) is not a short position: the fund
pledged that asset as collateral to borrow against it, and it cannot be reported
as both the asset and the cash raised, so the leg comes through negative and the
row still totals 100.

That makes signed summation the right default — the weights are a genuine
decomposition, so `participation_asset_weight` plus `interest_bearing_weight`
add back up to roughly 100, and the currency weights never exceed it. One fund
in the live universe reports 107.7% participation-compatible assets against a
7.8% borrowing leg, which is a coherent description of a collateralised book.

The interest screen is the single exception, because it asks a different
question: not "how much of the portfolio is this" but "is the fund party to this
kind of transaction at all". A repo entered from the borrowing side is still a
repo and the fund still pays interest on it, so the screen takes its magnitude.
Summing it signed would clear the participation screen for exactly the funds
that fail it.

**This is a composition screen, not a mandate check.** It answers "does this
fund hold interest-bearing instruments", not "is this fund marketed as a
participation fund". On the live universe the two agree closely — 120 of the 121
funds with "katılım" in their name are detected — but roughly 19 further funds
(pure gold, pure equity, index funds) hold no interest-bearing instruments
either and are flagged the same way. That is a true statement about what they
hold, not a claim about how they are sold.

The single declared fund that is *not* flagged is a fund-of-funds holding 82% in
other funds. It shows zero interest exposure, but almost none of its portfolio
is visible, so it lands in **Mixed** rather than being given a verdict the data
cannot support.

### `risk_band` — Conservative / Balanced / Aggressive / Specialised

Banded on growth-asset weight (equity + foreign equity + precious metals +
alternatives), with default edges at 10 / 35 / 65.

This is the one axis that accepts a data-driven method:

- `fixed` (default) — the configured edges. Comparable across periods.
- `quantile` — the universe's own quartiles.
- `kmeans1d` — natural breaks found by a 1-D KMeans.

Fixed is the default because moving edges make two reports incomparable: a fund
can change band without changing a single holding.

### `currency_band` — TRY / FX / Gold Weighted, or Mixed

Dominant currency exposure at or above `currency_band_threshold` (60%),
otherwise Mixed.

### `lookthrough_band` — Transparent / Partial / Heavy Look-through

Banded on the weight held in other funds and ETFs, default edges at 5 / 25.

## Model artifact

`AllocationClassifier.save()` writes JSON, not pickle — readable, diffable and
safe to load:

```json
{
  "artifact_version": 1,
  "config": { "...": "..." },
  "feature_names": ["Deposit", "Equity", "Fixed Income", "..."],
  "centroids": [[0.0, 88.4, 2.1, "..."]],
  "class_labels_en": ["Equity Weighted", "..."],
  "class_labels_tr": ["Hisse Senedi Ağırlıklı", "..."],
  "class_families": ["Equity", "..."],
  "fit_info": { "k": 8, "silhouette": 0.61, "n_funds": 392, "...": "..." }
}
```

Reusing a saved model is what makes period-over-period comparison work:

```bash
python scripts/classify_funds.py --db-path data/besfundlens.sqlite --lookback 3m \
  --fit --model-path models/allocation_classifier.json
```
```bash
python scripts/classify_funds.py --db-path data/besfundlens.sqlite --lookback 1m \
  --predict --model-path models/allocation_classifier.json --output reports/classification_1m.csv
```

The second run assigns funds to the classes the first run discovered instead of
finding new ones, so the class names mean the same thing in both reports.

## Output columns

| Column | Meaning |
|---|---|
| `asset_class`, `asset_class_tr` | model-derived class name |
| `asset_class_family` | level-1 family |
| `class_id` | cluster index (`-1` when unclassifiable) |
| `class_confidence` | 0–1, look-through discounted |
| `runner_up_class` | second-nearest class |
| `class_description` | centroid composition summary |
| `participation_class`, `risk_band`, `currency_band`, `lookthrough_band` | secondary axes (each with `_tr`) |
| `class_stability`, `style_drift`, `allocation_volatility`, `drift_flag` | stability metrics |
| `growth_asset_weight`, `interest_bearing_weight`, `lookthrough_weight`, `try_weight`, `fx_weight`, `gold_weight` | supporting weights |
| `n_observations`, `window_start`, `window_end`, `is_classifiable` | provenance |

Funds with no usable allocation data in the window get `is_classifiable=False`
and a blank verdict rather than a confident-looking label derived from an
all-zero vector.

## Limitations

- **Look-through is flagged, not resolved.** TEFAS allocation data does not
  break down what an underlying fund holds. A fund-of-funds is classified by the
  fact that it holds funds, which is much less informative than knowing what
  those funds hold. The look-through band and the confidence discount mark this
  gap; they do not close it.
- **Allocation only.** No return, volatility or tracking-error input. Two funds
  with identical allocations and very different management land in the same
  class.
- **Published data.** Classification reflects what was published on the
  observation dates, including any late corrections not yet applied.
- **Class names are descriptive, not regulatory.** They are derived from
  holdings and do not correspond to any official fund category.

Classification is descriptive analytics on published allocation data. It is not
investment advice.
