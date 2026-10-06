"""
Stress signals read the path between a window's endpoints. Each case is built
so that the answer is known: a universe that is quiet until one day, a fund
that deals daily and then stops, a fund that takes money in and then loses it.
"""

import pandas as pd
import pytest

from besfundlens.core.stress import (
    EVENT_RUN,
    EVENT_SHOCK,
    EVENT_MANUAL,
    freezes,
    daily_panel,
    fund_founder,
    stress_signals,
)

DAYS = pd.bdate_range("2026-01-01", periods=40)
EVENT_DAY = 30
FUNDS = 40


def universe(price_drop_on=None, outflow_after=None, share=0.5):
    """
    FUNDS funds over DAYS, every one taking in a little money every day.

    ``price_drop_on`` knocks 10% off the price of ``share`` of the funds on that
    day; ``outflow_after`` has the same funds lose 20% of their units the day
    after. Everything else stays quiet.
    """
    rows = []
    hit = int(FUNDS * share)
    for f in range(FUNDS):
        price, units = 1.0, 10_000_000.0
        for d, day in enumerate(DAYS):
            if d > 0:
                units *= 1.001
                if f < hit and price_drop_on is not None and d == price_drop_on:
                    price *= 0.90
                if f < hit and outflow_after is not None and d == outflow_after + 1:
                    units *= 0.80
            rows.append(
                {
                    "fonKodu": f"F{f:02d}",
                    "fonUnvan": f"TEST{f % 4} PORTFÖY FON {f}",
                    "tarih": day,
                    "fiyat": price,
                    "tedPaySayisi": units,
                    "kisiSayisi": 100 + d,
                    "portfoyBuyukluk": price * units,
                }
            )
    return pd.DataFrame(rows)


def window(df, **kwargs):
    return stress_signals(df, DAYS[20], DAYS[-1], **kwargs)


# ------------------------------------------------------------------ founder


@pytest.mark.parametrize(
    "name, founder",
    [
        ("TERA PORTFÖY FON SEPETİ FONU", "TERA PORTFÖY"),
        ("İŞ PORTFÖY BİRİNCİ PARA PİYASASI SERBEST (TL) FON", "İŞ PORTFÖY"),
        ("AZİMUT PYŞ KISA VADELİ BORÇLANMA ARAÇLARI FONU", "AZİMUT PYŞ"),
        (
            "HDI FİBA EMEKLİLİK VE HAYAT A.Ş. TACİRLER PORTFÖY DEĞİŞKEN EMEKLİLİK YATIRIM FONU",
            "HDI FİBA EMEKLİLİK VE HAYAT",
        ),
    ],
)
def test_the_founder_is_read_from_the_front_of_the_name(name, founder):
    """A pension fund's name can mention a portfolio manager after its founder."""
    assert fund_founder(name) == founder


# ------------------------------------------------------------------ event


def test_a_price_shock_followed_by_outflows_is_a_run():
    result = window(universe(price_drop_on=EVENT_DAY, outflow_after=EVENT_DAY))

    assert result["event_date"] == DAYS[EVENT_DAY]
    assert result["event_kind"] == EVENT_RUN


def test_a_price_shock_nobody_runs_from_is_a_shock():
    """What BES looks like: prices fall, but its outflows are restricted."""
    result = window(universe(price_drop_on=EVENT_DAY))

    assert result["event_date"] == DAYS[EVENT_DAY]
    assert result["event_kind"] == EVENT_SHOCK


def test_a_quiet_window_has_no_event():
    result = window(universe())

    assert result["event_date"] is None
    assert result["event_kind"] is None
    assert result["funds"]["flow_before"].isna().all()


def test_a_fixed_event_date_is_used_as_given():
    fixed = DAYS[25]
    result = window(universe(price_drop_on=EVENT_DAY, outflow_after=EVENT_DAY), event_date=fixed)

    assert result["event_date"] == fixed
    assert result["event_kind"] == EVENT_MANUAL


# ------------------------------------------------------------------ flows around it


def test_inflow_before_and_outflow_after_is_a_turn():
    df = universe(price_drop_on=EVENT_DAY, outflow_after=EVENT_DAY)

    # One fund doubles its units in the week before the event, then loses
    # a third of them the day after it
    fund = df["fonKodu"].eq("F00")
    days = df["tarih"]
    df.loc[fund & days.between(DAYS[24], DAYS[EVENT_DAY - 1]), "tedPaySayisi"] *= 2.0
    df.loc[fund & days.ge(DAYS[EVENT_DAY + 1]), "tedPaySayisi"] *= 2.0 * 0.6
    df.loc[fund, "portfoyBuyukluk"] = df.loc[fund, "fiyat"] * df.loc[fund, "tedPaySayisi"]

    funds = window(df)["funds"].set_index("fonKodu")

    assert funds.loc["F00", "flow_before"] > 0.9
    assert funds.loc["F00", "flow_after"] < -0.3
    assert funds.loc["F00", "turned"]
    assert not funds.loc["F39", "turned"]


def test_the_event_day_counts_as_after():
    """Splitting the shock from the reaction to it would hide both."""
    df = universe(price_drop_on=EVENT_DAY, outflow_after=EVENT_DAY - 1)
    funds = window(df, event_date=DAYS[EVENT_DAY])["funds"].set_index("fonKodu")

    # The outflow lands on the event day itself, so all of it is after
    assert funds.loc["F00", "flow_after"] < -0.15
    assert funds.loc["F00", "flow_before"] > 0


# ------------------------------------------------------------------ freezes


def freeze(df, code, from_day, stale_price=False):
    """Stop a fund's units and investors from moving, as a gate would."""
    fund = df["fonKodu"].eq(code)
    after = fund & df["tarih"].ge(DAYS[from_day])
    held = df.loc[fund & df["tarih"].eq(DAYS[from_day - 1])].iloc[0]
    df.loc[after, "tedPaySayisi"] = held["tedPaySayisi"]
    df.loc[after, "kisiSayisi"] = held["kisiSayisi"]
    if stale_price:
        df.loc[after, "fiyat"] = held["fiyat"]
    else:
        df.loc[after, "fiyat"] = held["fiyat"] * (1 - 0.01 * (df.loc[after, "tarih"].rank()))
    df.loc[fund, "portfoyBuyukluk"] = df.loc[fund, "fiyat"] * df.loc[fund, "tedPaySayisi"]
    return df


def test_a_fund_that_stops_dealing_is_frozen():
    df = freeze(universe(), "F05", from_day=32)
    funds = window(df)["funds"].set_index("fonKodu")

    assert funds.loc["F05", "frozen"]
    assert funds.loc["F05", "frozen_since"] == DAYS[32]
    assert funds.loc["F05", "frozen_days"] == len(DAYS) - 32
    assert funds.loc["F05", "frozen_ongoing"]
    assert not funds.loc["F06", "frozen"]


def test_a_fund_whose_price_also_stops_is_stale_not_frozen():
    """Nothing moving at all is old data repeated, not a fund closed to dealing."""
    df = freeze(universe(), "F05", from_day=32, stale_price=True)
    assert not window(df)["funds"].set_index("fonKodu").loc["F05", "frozen"]


def test_a_fund_that_never_dealt_daily_is_not_frozen():
    """Private funds whose units sit still for weeks are normal, not gated."""
    df = universe()
    fund = df["fonKodu"].eq("F07")
    df.loc[fund, "tedPaySayisi"] = 10_000_000.0
    df.loc[fund, "kisiSayisi"] = 3
    df.loc[fund, "fiyat"] = 1 + 0.001 * df.loc[fund, "tarih"].rank()

    assert freezes(daily_panel(df)).query("fonKodu == 'F07'").empty


# ------------------------------------------------------------------ unpublished


def test_a_zero_price_is_counted_not_read_as_a_crash():
    """A suspended fund's zero price must not show up as a price drop."""
    df = universe()
    halted = df["fonKodu"].lt("F20") & df["tarih"].ge(DAYS[EVENT_DAY])
    df.loc[halted, ["fiyat", "tedPaySayisi", "portfoyBuyukluk"]] = 0.0

    result = window(df)

    assert result["event_date"] is None
    assert result["funds"]["unpublished"].sum() == 20


def test_founders_are_summed_and_ordered_by_stressed_aum():
    df = freeze(universe(), "F01", from_day=32)  # F01 belongs to TEST1 PORTFÖY
    founders = window(df)["founders"].set_index("founder")

    assert founders.loc["TEST1 PORTFÖY", "frozen"] == 1
    assert founders.loc["TEST1 PORTFÖY", "funds"] == FUNDS // 4
    assert founders.index[0] == "TEST1 PORTFÖY"
