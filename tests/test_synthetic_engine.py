from __future__ import annotations

import pandas as pd

from turkeyfundlens.core.engine import (
    initialize_engine,
    run_universe_analysis,
    compare_funds,
    selected_funds_report_to_markdown,
)


def test_synthetic_engine_smoke():
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
    df_general = pd.DataFrame({
        "fonKodu": ["AAA"] * 4,
        "fonUnvan": ["Test Fund"] * 4,
        "tarih": dates,
        "fiyat": [1.00, 1.01, 1.02, 1.03],
        "tedPaySayisi": [1000, 1010, 1020, 1030],
        "kisiSayisi": [10, 11, 11, 12],
        "portfoyBuyukluk": [1000.0, 1020.1, 1040.4, 1060.9],
    })
    df_allocation = pd.DataFrame({
        "fonKodu": ["AAA"] * 4,
        "fonUnvan": ["Test Fund"] * 4,
        "tarih": dates,
        "dt": [80, 80, 80, 80],
        "hs": [20, 20, 20, 20],
    })

    initialize_engine(df_general, df_allocation)
    result = run_universe_analysis(lookback=2, valid_only=False, top_n=3)
    assert result["lens_universe_df"].shape[0] == 1

    comparison = compare_funds(["AAA"], lookback=2)
    assert comparison.shape[0] == 1
    assert "market_flow_quadrant" in comparison.columns

    tr_report = selected_funds_report_to_markdown(comparison, language="tr")
    assert "# Seçili Fon Karşılaştırma Raporu" in tr_report
