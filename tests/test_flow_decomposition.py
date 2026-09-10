"""
The AUM decomposition is the claim the project is built on: that a fund's AUM
change can be split into what the market did and what investors did. The engine
had one smoke test that checked shapes, so the arithmetic itself was never
asserted anywhere. These pin it down.

Each case is built so the right answer is known by construction:
AUM is price times units, so moving one at a time isolates one side of the split.
"""

import pandas as pd
import pytest

from besfundlens.core.engine import initialize_engine, run_universe_analysis


def analyse(prices, units, participants=None, lookback=None):
    """Run one synthetic fund through the engine and return its universe row."""
    dates = pd.to_datetime([f"2026-01-{day:02d}" for day in range(1, len(prices) + 1)])
    participants = participants or [10] * len(prices)

    df_general = pd.DataFrame(
        {
            "fonKodu": ["AAA"] * len(dates),
            "fonUnvan": ["Test Fund"] * len(dates),
            "tarih": dates,
            "fiyat": prices,
            "tedPaySayisi": units,
            "kisiSayisi": participants,
            "portfoyBuyukluk": [p * u for p, u in zip(prices, units)],
        }
    )
    df_allocation = pd.DataFrame(
        {
            "fonKodu": ["AAA"] * len(dates),
            "fonUnvan": ["Test Fund"] * len(dates),
            "tarih": dates,
            "dt": [100] * len(dates),
        }
    )

    initialize_engine(df_general, df_allocation)
    result = run_universe_analysis(lookback=lookback or len(dates) - 1, valid_only=False)
    return result["lens_universe_df"].iloc[0]


def test_a_price_only_move_is_all_market_effect():
    """Units held constant: nobody bought or sold, so flow must be zero."""
    fund = analyse(prices=[1.0, 1.05, 1.10], units=[1000, 1000, 1000])

    assert fund["aum_change_pct"] == pytest.approx(0.10, abs=1e-6)
    assert fund["market_effect_pct"] == pytest.approx(0.10, abs=1e-6)
    assert fund["flow_pct"] == pytest.approx(0.0, abs=1e-6)


def test_a_unit_only_move_is_all_investor_flow():
    """Price held constant: the market did nothing, so the whole change is flow."""
    fund = analyse(prices=[1.0, 1.0, 1.0], units=[1000, 1050, 1100])

    assert fund["aum_change_pct"] == pytest.approx(0.10, abs=1e-6)
    assert fund["market_effect_pct"] == pytest.approx(0.0, abs=1e-6)
    assert fund["flow_pct"] == pytest.approx(0.10, abs=1e-6)


def test_the_two_parts_add_up_to_the_whole():
    """
    Price and units both up a tenth. AUM is their product, so it is up 21%, and
    the split has to account for all of it rather than 20%.
    """
    fund = analyse(prices=[1.0, 1.05, 1.10], units=[1000, 1050, 1100])

    assert fund["aum_change_pct"] == pytest.approx(0.21, abs=1e-6)
    assert fund["market_effect_pct"] + fund["flow_pct"] == pytest.approx(
        fund["aum_change_pct"], abs=1e-6
    )


def test_outflow_is_reported_as_negative_flow():
    """A fund can rise on price while investors leave; the signs must not cancel."""
    fund = analyse(prices=[1.0, 1.10, 1.20], units=[1000, 950, 900])

    assert fund["market_effect_pct"] > 0
    assert fund["flow_pct"] < 0
    assert fund["market_effect_pct"] + fund["flow_pct"] == pytest.approx(
        fund["aum_change_pct"], abs=1e-6
    )


def test_flow_in_lira_agrees_with_flow_in_percent():
    """total_net_flow is the same number as flow_pct, scaled by starting AUM."""
    fund = analyse(prices=[1.0, 1.0, 1.0], units=[1000, 1050, 1100])

    assert fund["total_net_flow"] == pytest.approx(
        fund["flow_pct"] * fund["start_aum"], rel=1e-6
    )
    assert fund["total_market_effect"] == pytest.approx(
        fund["market_effect_pct"] * fund["start_aum"], rel=1e-6
    )


def test_a_fund_growing_on_flows_in_a_falling_market_lands_in_that_quadrant():
    """The case the project exists to surface."""
    fund = analyse(prices=[1.0, 0.95, 0.90], units=[1000, 1200, 1400])

    assert fund["market_effect_pct"] < 0
    assert fund["flow_pct"] > 0
    assert fund["market_flow_quadrant"] == "Negative Market / Positive Flow"


def test_participant_change_is_tracked_separately_from_flow():
    """Money can arrive without new participants; the two are different columns."""
    fund = analyse(
        prices=[1.0, 1.0, 1.0],
        units=[1000, 1100, 1200],
        participants=[10, 10, 10],
    )

    assert fund["flow_pct"] > 0
    assert fund["participant_change"] == 0
    assert fund["participant_change_pct"] == pytest.approx(0.0, abs=1e-9)


def test_a_lookback_longer_than_the_data_says_so_clearly():
    """
    Asking for more history than is loaded used to surface as a KeyError on
    start_aum several frames deep, which says nothing about what to change.
    """
    with pytest.raises(ValueError, match="longer than the loaded data"):
        analyse(prices=[1.0, 1.01, 1.02], units=[1000, 1000, 1000], lookback=120)
