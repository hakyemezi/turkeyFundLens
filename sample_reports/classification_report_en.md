# besFundLens Allocation Classification Report

## Asset Allocation Classes

| Asset Class | Family | Fund Count | Avg Confidence | Avg Stability |
|---|---|---:|---:|---:|
| Equity Weighted | Equity | 141 | 0.60 | 0.99 |
| Fixed Income Weighted | Fixed Income | 141 | 0.59 | 0.99 |
| Lease Certificates Tilted Multi-Asset | Fixed Income | 68 | 0.56 | 1.00 |
| Precious Metals Weighted | Precious Metals | 25 | 0.73 | 0.99 |
| Fund Tilted Multi-Asset | Fund of Funds | 24 | 0.09 | 0.99 |

## Risk Bands

| Risk Band | Fund Count |
|---|---:|
| Specialised | 123 |
| Conservative | 116 |
| Balanced | 88 |
| Aggressive | 72 |

## Currency Exposure Bands

| Currency Band | Fund Count |
|---|---:|
| TRY Weighted | 303 |
| Mixed Currency | 45 |
| FX Weighted | 29 |
| Gold Weighted | 22 |

## Participation vs Conventional

| Participation | Fund Count |
|---|---:|
| Conventional | 261 |
| Participation | 132 |
| Mixed | 5 |
| Unknown | 1 |

## Style Drift Watchlist

| Fund | Asset Class | Style Drift | Stability | Confidence |
|---|---|---:|---:|---:|
| AEZ | Equity Weighted | 189.2 | 0.75 | 0.07 |
| TNE | Equity Weighted | 124.5 | 1.00 | 0.41 |
| AUG | Fixed Income Weighted | 89.7 | 1.00 | 0.53 |
| BBD | Equity Weighted | 85.0 | 1.00 | 0.77 |
| AVJ | Lease Certificates Tilted Multi-Asset | 60.0 | 1.00 | 0.29 |
| GGJ | Precious Metals Weighted | 49.8 | 0.75 | 0.24 |
| ACV | Lease Certificates Tilted Multi-Asset | 49.6 | 1.00 | 0.32 |
| VEY | Lease Certificates Tilted Multi-Asset | 47.7 | 1.00 | 0.10 |
| RZN | Fund Tilted Multi-Asset | 45.9 | 1.00 | 0.11 |
| IEE | Equity Weighted | 45.3 | 1.00 | 0.63 |

## Classification Quality

- Model: **KMeans over window-averaged allocation vectors**
- Class count (k): **5**
- Silhouette score: **0.523**
- Classified funds: **399**
- Classification window: **2026-05-08 - 2026-08-07**
- Low-confidence funds: **53**
- Heavy look-through funds: **30**

## Classification Notes

- Classes are discovered by clustering window-averaged allocation vectors; class names are derived from each cluster centroid.
- `Confidence` is the margin between the nearest and second-nearest class, discounted by the share of the portfolio held in other funds.
- `Stability` is the share of sub-windows in which the fund stayed in its own class.
- `Style Drift` is the allocation distance between the first and last sub-window, in percentage points.
- Classification is descriptive analytics on published allocation data. It is not investment advice.