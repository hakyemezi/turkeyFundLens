"""
Measuring between two dates rather than over the latest N trading days.

The page asks "what happened since 17 September", which a lookback cannot
answer: twenty trading days ending today start wherever they start. These pin
down that a window starts and ends where it was asked to, that nothing after the
end date leaks into it, and that it refuses a window with nothing to measure.
"""

import pandas as pd
import pytest

from turkeyfundlens.core.engine import (
    run_universe_analysis_from_dataframes,
    slice_date_window,
)

# Ten business days, Thursday 1 to Wednesday 14 January 2026
DATES = pd.bdate_range("2026-01-01", periods=10)


def frames(funds):
    """
    Build the two source frames from {code: (dates, prices, allocation)}.

    ``allocation`` is a list of {asset_code: weight} dicts, one per date.
    Units are held constant, so every move is market effect.
    """
    general, allocation = [], []
    for code, (dates, prices, weights) in funds.items():
        for day, price, row in zip(dates, prices, weights):
            general.append(
                {
                    "fonKodu": code,
                    "fonUnvan": f"Fund {code}",
                    "tarih": day,
                    "fiyat": price,
                    "tedPaySayisi": 1000.0,
                    "kisiSayisi": 10,
                    "portfoyBuyukluk": price * 1000,
                }
            )
            allocation.append({"fonKodu": code, "fonUnvan": f"Fund {code}", "tarih": day, **row})
    return pd.DataFrame(general), pd.DataFrame(allocation).fillna(0)


def one_fund(prices=None, weights=None, dates=DATES):
    prices = prices or [1.0 + 0.01 * i for i in range(len(dates))]
    weights = weights or [{"dt": 100}] * len(dates)
    return frames({"AAA": (dates, prices, weights)})


def analyse(df_general, df_allocation, start, end):
    result = run_universe_analysis_from_dataframes(
        df_general,
        df_allocation,
        valid_only=False,
        start_date=start,
        end_date=end,
    )
    return result


def test_the_window_starts_and_ends_on_the_dates_asked_for():
    df_general, df_allocation = one_fund()
    result = analyse(df_general, df_allocation, DATES[2], DATES[6])
    fund = result["lens_universe_df"].iloc[0]

    assert fund["start_date"] == DATES[2]
    assert fund["end_date"] == DATES[6]
    assert result["lookback_intervals"] == 4
    assert fund["cumulative_return"] == pytest.approx(1.06 / 1.02 - 1, abs=1e-9)


def test_nothing_after_the_end_date_leaks_in():
    """
    The allocation flips from bonds to equity after the window ends. The DNA
    snapshot reads the last row it is given, so without the cut it would report
    the fund as it is today rather than as it was on the end date.
    """
    weights = [{"dt": 100}] * 5 + [{"hs": 100}] * 5
    df_general, df_allocation = one_fund(weights=weights)
    fund = analyse(df_general, df_allocation, DATES[0], DATES[4])["lens_universe_df"].iloc[0]

    assert fund["end_date"] == DATES[4]
    assert fund["top_asset_group"] == "Fixed Income"


def test_a_start_on_a_weekend_takes_the_next_published_day_as_the_base():
    df_general, df_allocation = one_fund()
    saturday = pd.Timestamp("2026-01-03")
    fund = analyse(df_general, df_allocation, saturday, DATES[-1])["lens_universe_df"].iloc[0]

    assert fund["start_date"] == pd.Timestamp("2026-01-05")


def test_a_fund_launched_inside_the_window_is_left_out():
    """It has no price on the start date, so it has no change to report."""
    df_general, df_allocation = frames(
        {
            "OLD": (DATES, [1.0] * 10, [{"dt": 100}] * 10),
            "NEW": (DATES[5:], [1.0] * 5, [{"dt": 100}] * 5),
        }
    )
    universe = analyse(df_general, df_allocation, DATES[0], DATES[-1])["lens_universe_df"]

    assert universe["fonKodu"].tolist() == ["OLD"]


def test_a_window_reaching_the_latest_day_matches_the_lookback_over_it():
    df_general, df_allocation = one_fund()
    by_dates = analyse(df_general, df_allocation, DATES[3], DATES[-1])["lens_universe_df"].iloc[0]
    by_lookback = run_universe_analysis_from_dataframes(
        df_general, df_allocation, lookback=6, valid_only=False
    )["lens_universe_df"].iloc[0]

    for column in ("start_date", "end_date", "cumulative_return", "market_effect_pct", "flow_pct"):
        assert by_dates[column] == by_lookback[column], column


def test_a_window_with_one_published_day_says_so():
    df_general, df_allocation = one_fund()
    with pytest.raises(ValueError, match="at least two"):
        slice_date_window(df_general, df_allocation, DATES[4], DATES[4])


def test_a_window_outside_the_data_says_so():
    """What dates past the end of a cache look like."""
    df_general, df_allocation = one_fund()
    with pytest.raises(ValueError, match="0 published day"):
        slice_date_window(df_general, df_allocation, "2026-03-01", "2026-03-31")


def test_a_start_after_the_end_is_refused():
    df_general, df_allocation = one_fund()
    with pytest.raises(ValueError, match="after end_date"):
        slice_date_window(df_general, df_allocation, DATES[5], DATES[1])


def test_string_dates_from_a_cache_are_cut_the_same_way():
    """SQLite hands tarih back as text; the cut must not depend on the dtype."""
    df_general, df_allocation = one_fund()
    df_general["tarih"] = df_general["tarih"].dt.strftime("%Y-%m-%d")
    df_allocation["tarih"] = df_allocation["tarih"].dt.strftime("%Y-%m-%d")

    cut_general, cut_allocation, intervals = slice_date_window(
        df_general, df_allocation, "2026-01-05", "2026-01-09"
    )

    assert len(cut_general) == len(cut_allocation) == 5
    assert intervals == 4


def test_a_zero_price_is_an_unpublished_day_not_a_total_loss():
    """
    TEFAS publishes a price of zero for a fund that is suspended or matured.
    Read as a price, the fund lost everything and the universe totals with it;
    it is dropped as a missing day instead, and named so the page can say so.
    """
    df_general, df_allocation = frames(
        {
            "LIVE": (DATES, [1.0] * 10, [{"dt": 100}] * 10),
            "HALT": (DATES, [1.0] * 6 + [0.0] * 4, [{"hs": 100}] * 10),
        }
    )
    df_general.loc[df_general["fiyat"].eq(0), ["tedPaySayisi", "portfoyBuyukluk"]] = 0

    result = analyse(df_general, df_allocation, DATES[0], DATES[-1])
    universe = result["lens_universe_df"]

    assert universe["fonKodu"].tolist() == ["LIVE"]
    assert result["unpublished_funds"] == ["HALT"]
    assert universe["cumulative_return"].min() > -1


def test_a_window_ending_before_the_halt_still_measures_the_fund():
    df_general, df_allocation = frames(
        {"HALT": (DATES, [1.0, 1.1, 1.2, 1.3] + [0.0] * 6, [{"hs": 100}] * 10)}
    )
    fund = analyse(df_general, df_allocation, DATES[0], DATES[3])["lens_universe_df"].iloc[0]

    assert fund["cumulative_return"] == pytest.approx(0.3, abs=1e-9)


def test_a_matured_fund_placeholder_is_not_a_market_crash():
    """
    A matured fund is left on TEFAS at price 1, 0.01 units and 0.01 TL. From a
    price of 55 that reads as a -98% market move unless it is dropped.
    """
    df_general, df_allocation = frames(
        {
            "LIVE": (DATES, [1.0] * 10, [{"dt": 100}] * 10),
            "DONE": (DATES, [55.0] * 8 + [1.0] * 2, [{"eut": 100}] * 10),
        }
    )
    done = df_general["fonKodu"].eq("DONE") & df_general["fiyat"].eq(1.0)
    df_general.loc[done, ["tedPaySayisi", "portfoyBuyukluk"]] = 0.01

    result = analyse(df_general, df_allocation, DATES[0], DATES[-1])

    assert result["lens_universe_df"]["fonKodu"].tolist() == ["LIVE"]
    assert result["unpublished_funds"] == ["DONE"]


def test_unpublished_days_can_be_kept_as_published():
    """
    Whether to drop them is the reader's call; the page asks. Kept, the zero is
    read as TEFAS published it — a total loss — which is what the engine did
    before these days were recognised at all.
    """
    df_general, df_allocation = frames(
        {"HALT": (DATES, [1.0] * 6 + [0.0] * 4, [{"hs": 100}] * 10)}
    )
    df_general.loc[df_general["fiyat"].eq(0), ["tedPaySayisi", "portfoyBuyukluk"]] = 0

    result = run_universe_analysis_from_dataframes(
        df_general,
        df_allocation,
        valid_only=False,
        start_date=DATES[0],
        end_date=DATES[-1],
        include_unpublished=True,
    )
    fund = result["lens_universe_df"].iloc[0]

    assert fund["cumulative_return"] == pytest.approx(-1.0)
    assert result["unpublished_funds"] == ["HALT"]
