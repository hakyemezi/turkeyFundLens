"""
Work out the numbers behind the September 2026 analysis page, once.

The daily pages cover a rolling month and change every evening. This page is
about one event and must not: it is computed here from a fixed window and
written to site/analysis/eylul-2026-fon-krizi.json, which the site build then
only renders. Nothing in the JSON is typed in by hand except the official
record, and that carries its sources.

    python site/make_crisis_analysis.py [--cache-dir DIR]

The page it feeds stays out of the site until "published" is set to true in the
JSON: it names fund companies next to a regulator's decision, and what it says
should be read by a person before it is public.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402  (a sibling file, not a package)
from turkeyfundlens.core.stress import daily_panel, stress_signals  # noqa: E402

START = pd.Timestamp("2026-09-01")
END = pd.Timestamp("2026-10-13")
OUT = HERE / "analysis" / "eylul-2026-fon-krizi.json"
LIQUIDATION_LIST = HERE / "analysis" / "spk-2026-60-tasfiye-listesi.txt"

# The founders named in SPK Bülteni 2026/60, as their names lead the fund
# titles on TEFAS. The bulletin writes "A1 Portföy Yönetimi A.Ş."; its funds
# are titled "A1 CAPİTAL PORTFÖY ...".
SPK_FOUNDERS = [
    "TERA PORTFÖY",
    "PUSULA PORTFÖY",
    "HEDEF PORTFÖY",
    "ATLAS PORTFÖY",
    "A1 CAPİTAL PORTFÖY",
    "PARDUS PORTFÖY",
    "BULLS PORTFÖY",
]

OFFICIAL = {
    "bulletin": "Sermaye Piyasası Kurulu Bülteni 2026/60",
    "bulletin_date": "2026-09-17",
    "bulletin_url": "https://spk.gov.tr/data/6aab8e7b8f95db07100fd7b4/2026-60.pdf",
    "decisions": "57/1706 ve 57/1707",
    "founder_count": 7,
    "listed_funds": 130,
    "statement_url": "https://spk.gov.tr/duyurular/basin-duyurulari/2026/"
                     "tasfiye-konusu-fonlardaki-yatirimci-sayisina-iliskin-aciklama",
    "statement_date": "2026-09-23",
    "statement_funds": 131,
    "statement_investors": 455758,
}


def normalise(title: str) -> str:
    return re.sub(r"[^A-ZÇĞİÖŞÜ0-9]", "", str(title).upper())


def series(index: pd.DataFrame) -> dict:
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in index.index],
        "price_drop": [round(v * 100, 2) for v in index["price_drop_share"]],
        "outflow": [round(v * 100, 2) for v in index["outflow_share"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=None)
    args = parser.parse_args()

    # The same fetch the site uses: the window plus a month before it
    yat_general, _ = build.fetch("YAT", START, END, args.cache_dir)
    bes_general, _ = build.fetch("EMK", START, END, args.cache_dir)

    yat = stress_signals(yat_general, START, END)
    bes = stress_signals(bes_general, START, END)
    event = yat["event_date"]
    if event is None:
        raise SystemExit("No event detected in the window; nothing to write about.")

    funds = yat["funds"].copy()
    daily = yat["daily"]
    first_day = daily["tarih"].min()
    base_day = daily.loc[daily["tarih"] < event, "tarih"].max()

    listed_titles = [
        line.strip() for line in LIQUIDATION_LIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    code_of = {normalise(title): code for code, title in zip(funds["fonKodu"], funds["fonUnvan"])}
    listed_codes = {code_of[normalise(t)] for t in listed_titles if normalise(t) in code_of}

    funds["named"] = funds["founder"].isin(SPK_FOUNDERS)
    funds["flagged"] = funds["frozen"] | funds["unpublished"]
    funds["listed"] = funds["fonKodu"].isin(listed_codes)

    # How each fund dealt before the event, which is what the freeze test leans on
    panel = daily_panel(yat_general)
    before = panel[(panel["tarih"] < event) & panel["prev_tedPaySayisi"].notna()]
    funds = funds.merge(
        (1 - before.groupby("fonKodu")["still"].mean()).rename("activity_before"), on="fonKodu", how="left"
    ).merge(
        panel[panel["tarih"] < event].groupby("fonKodu")["kisiSayisi"].last().rename("holders_before"),
        on="fonKodu", how="left",
    )

    founder_of = funds.set_index("fonKodu")["founder"]
    flows = daily.assign(founder=daily["fonKodu"].map(founder_of))
    flows["named"] = flows["founder"].isin(SPK_FOUNDERS)
    is_before = (flows["tarih"] > first_day) & (flows["tarih"] < event)
    is_after = flows["tarih"] >= event

    def aum_by_founder(on_day):
        return flows[flows["tarih"] == on_day].groupby("founder")["portfoyBuyukluk"].sum()

    start_aum = aum_by_founder(first_day)
    base_aum = aum_by_founder(base_day)
    flow_before = flows[is_before].groupby("founder")["flow"].sum()
    flow_after = flows[is_after].groupby("founder")["flow"].sum()

    founders = []
    for name in SPK_FOUNDERS:
        own = funds[funds["founder"] == name]
        founders.append(
            {
                "name": name,
                "slug": build.slugify(name),
                "funds": int(len(own)),
                "listed": int(own["listed"].sum()),
                "frozen": int(own["frozen"].sum()),
                "unpublished": int(own["unpublished"].sum()),
                "flagged": int(own["flagged"].sum()),
                "start_aum": float(start_aum.get(name, 0.0)),
                "flow_before": float(flow_before.get(name, 0.0)),
                "flow_before_pct": float(flow_before.get(name, 0.0) / start_aum[name]) if start_aum.get(name) else None,
                "flow_after": float(flow_after.get(name, 0.0)),
                "flow_after_pct": float(flow_after.get(name, 0.0) / base_aum[name]) if base_aum.get(name) else None,
            }
        )
    founders.sort(key=lambda f: f["start_aum"], reverse=True)

    # Where money went after the event, outside the seven
    others_after = flow_after[~flow_after.index.isin(SPK_FOUNDERS)].sort_values(ascending=False)
    receivers = [
        {"name": name, "slug": build.slugify(name), "flow_after": float(value)}
        for name, value in others_after.head(8).items()
    ]

    named, rest = funds[funds["named"]], funds[~funds["named"]]
    missed = named[~named["flagged"]]
    caught = named[named["flagged"]]

    # Net flow by day, in billions of lira: the seven founders' funds, and the rest
    after_first = flows["tarih"] > first_day
    seven_daily = flows[flows["named"] & after_first].groupby("tarih")["flow"].sum() / 1e9
    rest_daily = flows[~flows["named"] & after_first].groupby("tarih")["flow"].sum() / 1e9

    # How much of the rest's outflow after the event left money market funds,
    # going by the fund's own title
    title_of = funds.set_index("fonKodu")["fonUnvan"]
    rest_after = flows[~flows["named"] & is_after]
    money_market = rest_after["fonKodu"].map(title_of).str.contains("PARA PİYASASI", na=False)

    result = {
        "published": False,
        "slug": "eylul-2026-fon-krizi",
        "template": "crisis_2026_09.html",
        "title": "Eylül 2026’da TEFAS verisi ne gösterdi?",
        "computed": pd.Timestamp.now(tz="Europe/Istanbul").strftime("%Y-%m-%d"),
        "window": {"start": first_day.strftime("%Y-%m-%d"), "end": daily["tarih"].max().strftime("%Y-%m-%d")},
        "official": OFFICIAL,
        "event": {"date": event.strftime("%Y-%m-%d"), "kind": yat["event_kind"]},
        "bes_event": {
            "date": bes["event_date"].strftime("%Y-%m-%d") if bes["event_date"] is not None else None,
            "kind": bes["event_kind"],
            "frozen": int(bes["funds"]["frozen"].sum()),
            "unpublished": int(bes["funds"]["unpublished"].sum()),
        },
        "yat_index": series(yat["index"]),
        "bes_index": series(bes["index"]),
        "peak": {
            "price_drop_share": float(yat["index"].loc[event, "price_drop_share"]),
            "outflow_share_max": float(yat["index"].loc[yat["index"].index >= event, "outflow_share"].max()),
            "outflow_share_max_date": yat["index"].loc[yat["index"].index >= event, "outflow_share"].idxmax().strftime("%Y-%m-%d"),
            "bes_price_drop_share": float(bes["index"]["price_drop_share"].max()),
            "bes_outflow_share_max": float(bes["index"]["outflow_share"].max()),
        },
        "counts": {
            "funds": int(len(funds)),
            "named_funds": int(len(named)),
            "named_flagged": int(named["flagged"].sum()),
            "named_missed": int(len(missed)),
            "rest_funds": int(len(rest)),
            "rest_flagged": int(rest["flagged"].sum()),
            "flagged": int(funds["flagged"].sum()),
            "listed_titles": len(listed_titles),
            "listed_matched": len(listed_codes),
            "listed_flagged": int((funds["listed"] & funds["flagged"]).sum()),
        },
        "why_missed": {
            "missed_activity_median": float(missed["activity_before"].median()),
            "missed_holders_median": float(missed["holders_before"].median()),
            "missed_active_daily": int((missed["activity_before"] >= 0.8).sum()),
            "caught_activity_median": float(caught["activity_before"].median()),
            "caught_holders_median": float(caught["holders_before"].median()),
        },
        "totals": {
            "seven_start_aum": float(sum(f["start_aum"] for f in founders)),
            "seven_flow_before": float(sum(f["flow_before"] for f in founders)),
            "seven_flow_after": float(sum(f["flow_after"] for f in founders)),
            "rest_flow_before": float(flow_before[~flow_before.index.isin(SPK_FOUNDERS)].sum()),
            "rest_flow_after": float(others_after.sum()),
            "rest_money_market_after": float(rest_after.loc[money_market, "flow"].sum()),
        },
        "founders": founders,
        "receivers": receivers,
        "seven_daily": {
            "dates": [d.strftime("%Y-%m-%d") for d in seven_daily.index],
            "flow_bn": [round(float(v), 3) for v in seven_daily],
        },
        "rest_daily": {
            "dates": [d.strftime("%Y-%m-%d") for d in rest_daily.index],
            "flow_bn": [round(float(v), 3) for v in rest_daily],
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(json.dumps({k: result[k] for k in ("event", "bes_event", "counts", "why_missed", "totals")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
