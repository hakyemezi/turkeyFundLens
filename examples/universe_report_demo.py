from __future__ import annotations

from turkeyfundlens.workflows import run_universe_analysis_from_sqlite
from turkeyfundlens.core.engine import save_markdown_report

DB_PATH = "data/turkeyfundlens.sqlite"

result_en = run_universe_analysis_from_sqlite(DB_PATH, lookback="1m", language="en", top_n=10)
result_tr = run_universe_analysis_from_sqlite(DB_PATH, lookback="1m", language="tr", top_n=10)

save_markdown_report(result_en["markdown"], "sample_reports/market_report_en.md")
save_markdown_report(result_tr["markdown"], "sample_reports/market_report_tr.md")

print(result_en["markdown"][:2000])
print("\n--- Turkish sample ---\n")
print(result_tr["markdown"][:2000])
