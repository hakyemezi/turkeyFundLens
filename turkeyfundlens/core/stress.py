"""
Stress signals: what a window's two endpoints cannot show.

The engine measures each fund between the first and last day of a window. A
fund that doubled on inflows, lost a third of its money in one day and then
stopped dealing altogether can come out of that as "strong net inflow" — and
once a fund has stopped dealing, its flow is zero, so it looks calm. This
module reads the path between the endpoints instead:

- a daily stress score across the universe, and the day it peaks, which is
  taken as the event date unless the caller fixes one. Nothing about any
  particular crisis is built in; the date comes from the data on every run.
  A run — prices falling and investors leaving after — is told apart from a
  market shock nobody ran from, which is what BES shows: its outflows are
  restricted, so the same day reads as a shock there and a run elsewhere;
- each fund's flow before and after that date, and the funds that turned from
  heavy inflow to heavy outflow across it;
- funds whose units and investor count stopped moving while their price kept
  being published, which is what a fund that has stopped dealing looks like;
- all of it summed by founder, since a crisis tends to sit with a few fund
  companies rather than spread evenly.

Everything is read from the general frame alone; allocations play no part.
Rows TEFAS lists without a valuation (see ``unpublished_rows``) are never read
as prices here, whatever the analysis itself was told to do with them, and are
counted separately instead.
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from turkeyfundlens.core.engine import (
    UNIVERSE_MIN_START_AUM,
    add_flow_features,
    parse_tarih,
    unpublished_rows,
)

# A fund counts towards the daily score once it held at least this much the
# day before, so that a fund of a few thousand lira cannot swing a share.
MIN_AUM = UNIVERSE_MIN_START_AUM

# What a bad day for one fund is: its price down at least 3%, or investors
# taking out at least 5% of what it held the day before.
PRICE_DROP = -0.03
HEAVY_OUTFLOW = -0.05

# Redemptions settle a day or two after the orders that cause them, so the
# outflow that answers a price shock shows up after it.
OUTFLOW_LAG_DAYS = 2

# Each day is compared with the trading days before it, as a robust z-score:
# distance from their median, in units of their median absolute deviation.
BASELINE_DAYS = 20
MIN_BASELINE_DAYS = 10
# A floor on the deviation, in share of funds, so a run of identical quiet days
# does not turn the next small wobble into an infinite score.
MIN_DEVIATION = 0.005

# The run score is the smaller of the two z-scores — prices falling across the
# universe, and investors leaving in the days after — so a market drop that
# nobody runs from, and a month-end outflow nobody priced, both stay low. A
# day is a run when it reaches this, and failing any run, a market shock when
# the price z-score alone does.
EVENT_THRESHOLD = 4.0

EVENT_RUN = "run"
EVENT_SHOCK = "shock"
EVENT_MANUAL = "manual"

# A fund has stopped dealing when its units and investor count have not moved
# for this many published days running, while its price kept moving, and it
# had dealt on most days before that. The last condition keeps out the private
# and hedge funds whose units sit still for weeks as a matter of course.
FREEZE_MIN_DAYS = 5
FREEZE_MIN_ACTIVITY = 0.8
FREEZE_MIN_HISTORY = 10

# How far before the window the data is read: enough calendar days for the
# baseline and the freeze history, and no more, so a cache holding years does
# not have its longest freeze picked from some other year.
HISTORY_DAYS = 45

# A fund turned when it took in at least this much before the event and lost
# at least this much after it, each as a share of what it held at the time.
# It describes the event rather than detecting one: around an ordinary market
# drop about half as many funds turn as around the September 2026 run, at any
# threshold tried, so this one is set to keep the list short enough to read.
TURN_THRESHOLD = 0.20

# The founder leads the fund's name: up to "PORTFÖY" or "PYŞ" for a securities
# fund ("TERA PORTFÖY ..."), up to "A.Ş." for a pension fund ("ANADOLU HAYAT
# EMEKLİLİK A.Ş. ..."). Whichever ends first is the founder.
FOUNDER_PATTERNS = (
    re.compile(r"^(.*?\bPORTFÖY)\b"),
    re.compile(r"^(.*?\bPYŞ)\b"),
    re.compile(r"^(.*?)\s+A\.Ş\."),
)


def fund_founder(name: str) -> str:
    """The company that founded a fund, read from the front of its name."""
    name = str(name).strip()
    matches = [m for m in (p.match(name) for p in FOUNDER_PATTERNS) if m]
    if not matches:
        return name.split()[0] if name else ""
    return min(matches, key=lambda m: m.end()).group(1)


def daily_panel(df_general: pd.DataFrame) -> pd.DataFrame:
    """
    One row per fund and published day, with the day's flow and return.

    Built with the engine's own ``add_flow_features``, so a day's flow here is
    the same number the window totals are summed from.
    """
    df = df_general.copy()
    df["tarih"] = parse_tarih(df["tarih"]).dt.normalize()
    for column in ("fiyat", "tedPaySayisi", "kisiSayisi", "portfoyBuyukluk"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.loc[df["tarih"].notna() & ~unpublished_rows(df)]
    df = df.drop_duplicates(["fonKodu", "tarih"], keep="last")

    panel = add_flow_features(df)
    panel["flow"] = panel["estimated_net_flow_unit_method"]
    panel["flow_pct"] = panel["estimated_net_flow_unit_method_pct"]
    panel["still"] = (
        panel["tedPaySayisi"].eq(panel["prev_tedPaySayisi"])
        & panel["kisiSayisi"].eq(panel["prev_kisiSayisi"])
    )
    panel["price_moved"] = panel["fiyat"].ne(panel["prev_fiyat"])
    return panel


def _robust_z(series: pd.Series) -> pd.Series:
    previous = series.shift(1).rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_DAYS)
    median = previous.median()
    deviation = previous.apply(
        lambda values: np.median(np.abs(values - np.median(values))), raw=True
    ) * 1.4826
    return (series - median) / deviation.clip(lower=MIN_DEVIATION)


def stress_index(panel: pd.DataFrame) -> pd.DataFrame:
    """
    The universe's stress score for every published day.

    ``price_drop_share`` and ``outflow_share`` are the shares of funds having a
    bad day of each kind; ``stress`` is the smaller of their z-scores, with the
    outflow one taken as the worst of the day and the next few.
    """
    eligible = panel.loc[panel["prev_portfoyBuyukluk"].ge(MIN_AUM)]
    days = eligible.groupby("tarih").agg(
        funds=("fonKodu", "size"),
        price_drop_share=("fund_return", lambda r: r.le(PRICE_DROP).mean()),
        outflow_share=("flow_pct", lambda f: f.le(HEAVY_OUTFLOW).mean()),
    )
    days["price_z"] = _robust_z(days["price_drop_share"])
    days["outflow_z"] = _robust_z(days["outflow_share"])
    days["outflow_z_ahead"] = (
        days["outflow_z"][::-1].rolling(OUTFLOW_LAG_DAYS + 1, min_periods=1).max()[::-1]
    )
    days["stress"] = days[["price_z", "outflow_z_ahead"]].min(axis=1, skipna=False)
    return days


def detect_event(index: pd.DataFrame, start=None, end=None):
    """
    The event inside the window, as ``(date, kind)``, or ``(None, None)``.

    A run is the day the run score peaks, if it reaches the threshold. Failing
    that, a shock is the day the price z-score peaks, if that does.
    """
    window = index
    if start is not None:
        window = window.loc[window.index >= pd.Timestamp(start)]
    if end is not None:
        window = window.loc[window.index <= pd.Timestamp(end)]

    for column, kind in (("stress", EVENT_RUN), ("price_z", EVENT_SHOCK)):
        scores = window[column].dropna()
        if not scores.empty and scores.max() >= EVENT_THRESHOLD:
            return scores.idxmax(), kind
    return None, None


def freezes(panel: pd.DataFrame) -> pd.DataFrame:
    """
    The longest still spell of every fund that stopped dealing.

    One row per frozen fund: ``frozen_since`` and ``frozen_until`` are the
    first and last still day, ``frozen_days`` the number of published days it
    lasted, and ``frozen_ongoing`` whether it runs to the last day in the data.
    """
    last_day = panel["tarih"].max()
    rows = []
    for code, fund in panel.groupby("fonKodu", sort=False):
        still = fund["still"].to_numpy()
        if still.sum() < FREEZE_MIN_DAYS:
            continue

        # Longest run of consecutive still days
        best_start, best_length, run_start = None, 0, None
        for i, is_still in enumerate(still):
            if is_still:
                run_start = i if run_start is None else run_start
                if i - run_start + 1 > best_length:
                    best_start, best_length = run_start, i - run_start + 1
            else:
                run_start = None
        if best_length < FREEZE_MIN_DAYS:
            continue

        # It must have been dealing before, and its price still moving during
        history = fund.iloc[1:best_start]
        spell = fund.iloc[best_start:best_start + best_length]
        if len(history) < FREEZE_MIN_HISTORY:
            continue
        if (~history["still"]).mean() < FREEZE_MIN_ACTIVITY:
            continue
        if spell["price_moved"].mean() < 0.5:
            continue

        rows.append(
            {
                "fonKodu": code,
                "frozen_since": spell["tarih"].iloc[0],
                "frozen_until": spell["tarih"].iloc[-1],
                "frozen_days": best_length,
                "frozen_ongoing": spell["tarih"].iloc[-1] == last_day,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["fonKodu", "frozen_since", "frozen_until", "frozen_days", "frozen_ongoing"],
    )


def event_flows(panel: pd.DataFrame, event_date) -> pd.DataFrame:
    """
    Each fund's flow before and after the event, as a share of its AUM.

    The event day itself counts as after, so its move is not split from the
    reaction to it. Before runs from the window's first day to the day before
    the event, as a share of AUM on the first day; after runs from there to
    the end, as a share of AUM on the day before the event.
    """
    event = pd.Timestamp(event_date)
    first_day = panel["tarih"].min()
    before_days = panel["tarih"].lt(event)
    base_day = panel.loc[before_days, "tarih"].max()

    def aum_on(day):
        return panel.loc[panel["tarih"].eq(day)].set_index("fonKodu")["portfoyBuyukluk"]

    def share(rows, base):
        flows = rows.groupby("fonKodu")["flow"].sum(min_count=1)
        return flows / base.reindex(flows.index)

    before = share(panel.loc[before_days & panel["tarih"].gt(first_day)], aum_on(first_day))
    after = share(panel.loc[~before_days], aum_on(base_day))

    result = pd.DataFrame({"flow_before": before, "flow_after": after})
    result["turned"] = result["flow_before"].ge(TURN_THRESHOLD) & result["flow_after"].le(-TURN_THRESHOLD)
    return result.rename_axis("fonKodu").reset_index()


def stress_signals(
    df_general: pd.DataFrame,
    start_date,
    end_date,
    event_date=None,
) -> dict:
    """
    Everything above for one window.

    ``df_general`` may reach back before ``start_date``: those days give the
    stress score and the freeze test something to compare with, and nothing
    else is read from them. ``event_date`` fixes the event; left as None, it is
    detected, and may come back None if the window holds no stress worth the
    name.

    Returns a dict with ``event_date``, ``event_kind`` (``run``, ``shock``,
    ``manual`` or None), ``index`` (the daily scores inside the window),
    ``funds`` (one row per fund in the window), ``founders`` (the same summed
    by founder) and ``daily`` (each fund's published days in the window).
    """
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()

    dates = parse_tarih(df_general["tarih"]).dt.normalize()
    df_general = df_general.loc[dates.between(start - pd.Timedelta(days=HISTORY_DAYS), end)]

    panel = daily_panel(df_general)
    index = stress_index(panel)

    if event_date is None:
        event, kind = detect_event(index, start, end)
    else:
        event, kind = pd.Timestamp(event_date).normalize(), EVENT_MANUAL

    window = panel.loc[panel["tarih"].ge(start)]
    if window.empty:
        raise ValueError(f"No published day between {start.date()} and {end.date()}.")

    first_rows = window.groupby("fonKodu").first()
    funds = pd.DataFrame(
        {
            "fonUnvan": first_rows["fonUnvan"],
            "founder": first_rows["fonUnvan"].map(fund_founder),
            "start_aum": first_rows["portfoyBuyukluk"],
        }
    ).rename_axis("fonKodu").reset_index()

    # Funds TEFAS listed without a valuation inside the window
    raw = df_general.assign(tarih=parse_tarih(df_general["tarih"]).dt.normalize())
    raw = raw.loc[raw["tarih"].between(start, end)]
    unpublished = set(raw.loc[unpublished_rows(raw), "fonKodu"])
    funds["unpublished"] = funds["fonKodu"].isin(unpublished)

    # A freeze counts if any of it falls inside the window
    frozen = freezes(panel)
    frozen = frozen.loc[frozen["frozen_since"].le(end) & frozen["frozen_until"].ge(start)]
    funds = funds.merge(frozen, on="fonKodu", how="left")
    funds["frozen"] = funds["frozen_since"].notna()

    if event is not None and window["tarih"].min() < event:
        funds = funds.merge(event_flows(window, event), on="fonKodu", how="left")
    else:
        funds["flow_before"] = np.nan
        funds["flow_after"] = np.nan
        funds["turned"] = False
    funds["turned"] = funds["turned"].eq(True)

    return {
        "event_date": event,
        "event_kind": kind,
        "index": index.loc[index.index >= start],
        "funds": funds,
        "founders": founder_summary(funds, window, event),
        "daily": window[["fonKodu", "tarih", "fiyat", "tedPaySayisi", "kisiSayisi", "portfoyBuyukluk", "flow", "flow_pct"]],
    }


def founder_summary(funds: pd.DataFrame, window: pd.DataFrame, event) -> pd.DataFrame:
    """
    The fund-level signals summed by founder, worst first.

    ``stressed_aum`` is the founder's AUM at the start of the window held in
    funds that froze or went without a valuation, and ``stressed_aum_share``
    that as a share of all of it. Founders are ordered by the amount rather
    than the share, which would put a one-fund founder on top for one bad fund.
    """
    stressed = funds["frozen"] | funds["unpublished"]
    grouped = funds.assign(
        stressed_aum=funds["start_aum"].where(stressed, 0.0),
        frozen_n=funds["frozen"].astype(int),
        unpublished_n=funds["unpublished"].astype(int),
        turned_n=funds["turned"].astype(int),
    ).groupby("founder")

    summary = grouped.agg(
        funds=("fonKodu", "size"),
        start_aum=("start_aum", "sum"),
        frozen=("frozen_n", "sum"),
        unpublished=("unpublished_n", "sum"),
        turned=("turned_n", "sum"),
        stressed_aum=("stressed_aum", "sum"),
    )
    summary["stressed_aum_share"] = summary["stressed_aum"] / summary["start_aum"]

    summary["flow_after"] = np.nan
    if event is not None:
        after = window.loc[window["tarih"].ge(event)]
        base_day = window.loc[window["tarih"].lt(event), "tarih"].max()
        if pd.notna(base_day):
            founder_of = funds.set_index("fonKodu")["founder"]
            flows = after.groupby(after["fonKodu"].map(founder_of))["flow"].sum()
            base = window.loc[window["tarih"].eq(base_day)]
            base_aum = base.groupby(base["fonKodu"].map(founder_of))["portfoyBuyukluk"].sum()
            summary["flow_after"] = flows / base_aum

    return (
        summary.sort_values(["stressed_aum", "flow_after"], ascending=[False, True])
        .reset_index()
    )
