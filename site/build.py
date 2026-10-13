"""
Build the turkeyFundLens static site.

The Streamlit app answers questions on demand, but a page drawn in the browser
over a websocket is close to invisible to search engines, and the free host
puts it to sleep when nobody visits. Daily data does not need a server. This
fetches the last month from TEFAS once, runs the engine and the stress signals,
and writes plain HTML — a page per universe and one per fund — which GitHub
Pages serves as files. A scheduled workflow runs it every working evening.

    python site/build.py --out _site

The pages name funds and say things about them, in public, under a search
engine's eye. So the wording stays descriptive: what the published numbers
show, what is inferred from them and how, and where to check it.
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import shutil
import sys
import time
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from turkeyfundlens.config import FUND_TYPE_PENSION, FUND_TYPE_SECURITIES
from turkeyfundlens.core.engine import (
    UNIVERSE_MIN_START_AUM,
    run_universe_analysis_from_dataframes,
    translate_archetype,
    translate_flow_regime,
    translate_quadrant_name,
)
from turkeyfundlens.core.stress import (
    EVENT_RUN,
    EVENT_SHOCK,
    FREEZE_MIN_DAYS,
    HEAVY_OUTFLOW,
    PRICE_DROP,
    TURN_THRESHOLD,
    stress_signals,
)
from turkeyfundlens.data.tefas_client import FetchConfig, fetch_tefas_period, month_chunks

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from charts import bar_chart, line_chart  # noqa: E402  (a sibling file, not a package)

DEFAULT_BASE_URL = "https://hakyemezi.github.io/turkeyFundLens/"
APP_URL = "https://turkeyfundlens.streamlit.app"
REPO_URL = "https://github.com/hakyemezi/turkeyFundLens"

# Calendar days fetched before the window, for the stress baseline only
BASELINE_DAYS = 31

# TEFAS times out from GitHub's runners now and then, a whole month at a time.
# The client's own retries come first; a month that still comes back empty is
# asked for again this many times, this far apart, before the build gives up.
CHUNK_ROUNDS = 4
CHUNK_PAUSE_SECONDS = 60

# How many funds the lists of largest inflows and outflows run to
FLOW_LIST_LENGTH = 50

UNIVERSES = {
    FUND_TYPE_PENSION: {
        "slug": "bes",
        "name": "Emeklilik fonları (BES)",
        "plain": "emeklilik fonları",
        "short": "BES",
        "holders": "Katılımcı",
        "investors": False,
    },
    FUND_TYPE_SECURITIES: {
        "slug": "yat",
        "name": "Menkul kıymet yatırım fonları",
        "plain": "yatırım fonları",
        "short": "YAT",
        "holders": "Yatırımcı",
        "investors": True,
    },
}

MONTHS_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

# Said in plain words rather than as "crisis" or "shock": the site names funds
# and fund companies in public, and the label is an inference from prices.
EVENT_LABELS = {
    EVENT_RUN: "yaygın fiyat düşüşü ve ardından gelen çıkış dalgası",
    EVENT_SHOCK: "yaygın fiyat düşüşü; ardından çıkış dalgası gelmedi",
}

TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugify(text: str) -> str:
    """A founder's name as a URL: ASCII, lower case, hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", str(text).translate(TR_ASCII).lower()).strip("-")


# ------------------------------------------------------------------ formatting


def _tr_number(text: str) -> str:
    """1,234.56 -> 1.234,56"""
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def money(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    for limit, word in ((1e12, "trilyon"), (1e9, "milyar"), (1e6, "milyon")):
        if abs(value) >= limit:
            return f"{_tr_number(f'{value / limit:,.2f}')} {word} TL"
    return f"{_tr_number(f'{value:,.0f}')} TL"


def pct(value) -> str:
    """Decimals as Turkish percentages: 0.1234 -> %12,34, -0.05 -> -%5,00"""
    if value is None or pd.isna(value):
        return "—"
    value = float(value) * 100
    sign = "-" if value < 0 else ""
    return f"{sign}%{_tr_number(f'{abs(value):,.2f}')}"


def count(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return _tr_number(f"{int(value):,}")


def day(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = pd.Timestamp(value)
    return f"{value.day} {MONTHS_TR[value.month - 1]} {value.year}"


# ------------------------------------------------------------------ charts


def stress_chart(index: pd.DataFrame, event) -> str:
    return line_chart(
        index.index,
        {
            f"Fiyatı en az %{round(abs(PRICE_DROP) * 100)} düşen": index["price_drop_share"] * 100,
            f"En az %{round(abs(HEAVY_OUTFLOW) * 100)} çıkış yaşayan": index["outflow_share"] * 100,
        },
        event=event,
        y_title="Fonların oranı (%)",
        label="Kötü gün yaşayan fonların günlük oranı",
    )


def daily_flow_chart(daily: pd.DataFrame, event) -> str:
    daily = daily.dropna(subset=["flow_pct"])
    return bar_chart(
        daily["tarih"],
        daily["flow_pct"] * 100,
        event=event,
        y_title="Günlük tahmini akış (%)",
        label="Gün gün tahmini yatırımcı akışı",
    )


# ------------------------------------------------------------------ data


def fetch_strict(fund_type: str, start: pd.Timestamp, end: pd.Timestamp):
    """
    Every month between start and end, or an error.

    fetch_tefas_history skips a month that keeps failing and carries on, which
    suits a cache that can be topped up later but not a public page. The first
    build on GitHub lost the month before the window that way, and the site
    said no stress event had happened and showed a fund that had stopped
    dealing as an ordinary one. Here a missing month is asked for again, and
    if it still does not come, the build fails: Pages keeps serving the last
    good site, and GitHub mails the owner.

    Only a month made of today alone may come back empty: TEFAS may not have
    published the day yet when the build runs. It is asked for the same number
    of times first, since an empty answer and a timeout look alike from here,
    and the second build on GitHub lost a published day to a timeout.
    """
    config = FetchConfig(fund_type=fund_type)
    general, allocation = [], []
    for chunk_start, chunk_end in month_chunks(start, end):
        for attempt in range(1, CHUNK_ROUNDS + 1):
            df_general, df_allocation = fetch_tefas_period(chunk_start, chunk_end, config=config)
            if not df_general.empty and not df_allocation.empty:
                break
            if attempt == CHUNK_ROUNDS:
                if chunk_start == chunk_end == end:
                    print(f"  {fund_type} {end.date()}: still nothing; taking it as not published yet")
                    break
                raise RuntimeError(
                    f"TEFAS gave nothing for {fund_type} {chunk_start.date()} – "
                    f"{chunk_end.date()} after {CHUNK_ROUNDS} rounds; not building from "
                    "a partial month."
                )
            print(f"  {fund_type} {chunk_start.date()} – {chunk_end.date()} empty; "
                  f"asking again in {CHUNK_PAUSE_SECONDS}s ({attempt}/{CHUNK_ROUNDS})")
            time.sleep(CHUNK_PAUSE_SECONDS)
        general.append(df_general)
        allocation.append(df_allocation)
        time.sleep(config.success_sleep)

    frames = [frame for frame in general if not frame.empty]
    return (
        pd.concat(frames, ignore_index=True).drop_duplicates(),
        pd.concat([f for f in allocation if not f.empty], ignore_index=True).drop_duplicates(),
    )


def fetch(fund_type: str, start: pd.Timestamp, end: pd.Timestamp, cache_dir: Path | None):
    """The window plus its baseline, from TEFAS, or from a local pickle while developing."""
    cached = cache_dir / f"{fund_type}_{start.date()}_{end.date()}.pkl" if cache_dir else None
    if cached and cached.exists():
        return pickle.loads(cached.read_bytes())
    frames = fetch_strict(fund_type, start - pd.Timedelta(days=BASELINE_DAYS), end)
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(pickle.dumps(frames))
    return frames


def analyse(fund_type: str, start, end, cache_dir):
    info = UNIVERSES[fund_type]
    df_general, df_allocation = fetch(fund_type, start, end, cache_dir)
    if df_general.empty:
        raise RuntimeError(f"TEFAS returned nothing for {fund_type} {start.date()} – {end.date()}")

    result = run_universe_analysis_from_dataframes(
        df_general,
        df_allocation,
        valid_only=True,
        language="tr",
        start_date=start,
        end_date=end,
        classify=False,
    )
    stress = stress_signals(df_general, start, end)

    universe = result["lens_universe_df"].copy()
    universe["archetype"] = universe["archetype"].map(lambda v: translate_archetype(v, "tr"))
    universe["flow_regime"] = universe["flow_regime"].map(
        lambda v: translate_flow_regime(v, "tr", investors=info["investors"])
    )
    universe["market_flow_quadrant"] = universe["market_flow_quadrant"].map(
        lambda v: translate_quadrant_name(v, "tr")
    )
    universe = universe.merge(
        stress["funds"].drop(columns=["fonUnvan", "start_aum"]), on="fonKodu", how="left"
    )
    for flag in ("frozen", "frozen_ongoing", "turned", "unpublished"):
        universe[flag] = universe[flag].eq(True)

    # Where each fund stands among funds of its own type, and in the universe.
    # A return of 3% means little alone; "fourth of 120 money market funds" does.
    peers = universe.groupby("archetype")
    universe["peer_count"] = peers["fonKodu"].transform("size")
    universe["return_rank"] = peers["cumulative_return"].rank(ascending=False, method="min")
    universe["flow_rank"] = peers["flow_pct"].rank(ascending=False, method="min")
    universe["aum_rank"] = universe["end_aum"].rank(ascending=False, method="min")

    return {
        "fund_type": fund_type,
        "info": info,
        "universe": universe,
        "summary": result["market_report"]["universe_summary"],
        "stress": stress,
        "first_day": universe["start_date"].max(),
        "last_day": universe["end_date"].max(),
        "intervals": result["lookback_intervals"],
    }


# ------------------------------------------------------------------ pages


def fund_rows(analysis, sort="end_aum", ascending=False, limit=None):
    frame = analysis["universe"].sort_values(sort, ascending=ascending)
    if limit:
        frame = frame.head(limit)
    return frame.to_dict("records")


def fund_summary(row: dict, info: dict, first_day, last_day, fund_count: int) -> list[str]:
    """
    The fund's month in sentences built from its own numbers.

    Every fund page shares its layout with two thousand others; this is the
    part that is about this fund and no other, for a reader and for a search
    engine deciding whether the page says anything.
    """
    code = row["fonKodu"]
    sentences = []

    gain = row["cumulative_return"]
    if pd.notna(gain):
        verb = "değer kazandı" if gain >= 0 else "değer kaybetti"
        sentences.append(f"{code}, {day(first_day)} – {day(last_day)} arasında {pct(abs(gain))} {verb}.")

    sentences.append(
        f"Fonun büyüklüğü {money(row['start_aum'])} iken {money(row['end_aum'])} oldu; "
        f"değişim {pct(row['aum_change_pct'])}."
    )
    sentences.append(
        f"Bunun içinde piyasa etkisi {pct(row['market_effect_pct'])}, tahmini yatırımcı akışı "
        f"{pct(row['flow_pct'])} ({money(row['total_net_flow'])})."
    )

    change = row["participant_change"]
    if pd.notna(change):
        holders = info["holders"]
        moved = "değişmedi" if change == 0 else f"{count(abs(change))} {'arttı' if change > 0 else 'azaldı'}"
        sentences.append(f"{holders} sayısı {count(row['end_participants'])}; dönem içinde {moved}.")

    if row["peer_count"] >= 3 and pd.notna(row["return_rank"]) and pd.notna(row["flow_rank"]):
        sentences.append(
            f"Aynı tipteki {count(row['peer_count'])} fon ({row['archetype']}) arasında getiride "
            f"{count(row['return_rank'])}., yatırımcı akışında {count(row['flow_rank'])}. sırada."
        )
    sentences.append(
        f"Analiz edilen {count(fund_count)} fon içinde büyüklükte {count(row['aum_rank'])}. sırada."
    )
    return sentences


def similar_funds(universe: pd.DataFrame) -> dict:
    """For every fund, the funds of its type nearest to it in size."""
    nearest = {}
    for _, group in universe.sort_values("end_aum", ascending=False).groupby("archetype", sort=False):
        rows = group[["fonKodu", "fonUnvan"]].to_dict("records")
        for i, row in enumerate(rows):
            around = rows[max(0, i - 3):i] + rows[i + 1:i + 4]
            nearest[row["fonKodu"]] = around[:6]
    return nearest


def breadcrumb_items(items, base_url: str) -> list:
    """The trail of (name, path) pairs as schema.org ListItems; the last has no link."""
    return [
        {
            "@type": "ListItem",
            "position": position,
            "name": name,
            **({"item": base_url + ("" if href == "index.html" else href)} if href is not None else {}),
        }
        for position, (name, href) in enumerate(items, 1)
    ]


def universe_context(analysis):
    stress = analysis["stress"]
    funds = stress["funds"]
    event = stress["event_date"]

    frozen = funds[funds["frozen"]].sort_values("start_aum", ascending=False)
    turned = funds[funds["turned"]].sort_values("start_aum", ascending=False)
    unpublished = funds[funds["unpublished"]].sort_values("start_aum", ascending=False)
    founders = stress["founders"]
    founders = founders[founders[["frozen", "unpublished", "turned"]].sum(axis=1) > 0]

    return {
        **analysis,
        "event": event,
        "event_label": EVENT_LABELS.get(stress["event_kind"]),
        "event_at_start": event is not None and event <= analysis["first_day"],
        "stress_chart": stress_chart(stress["index"], event),
        "frozen": frozen.to_dict("records"),
        "turned": turned.to_dict("records"),
        "unpublished": unpublished.to_dict("records"),
        "founders": founders.head(25).to_dict("records"),
        "inflows": fund_rows(analysis, sort="total_net_flow", ascending=False, limit=15),
        "outflows": fund_rows(analysis, sort="total_net_flow", ascending=True, limit=15),
        "all_funds": fund_rows(analysis),
    }


def fund_contexts(ctx):
    """One context per fund that has any published day in the window."""
    universe = ctx["universe"].set_index("fonKodu", drop=False)
    stressed = ctx["stress"]["funds"].set_index("fonKodu")
    daily = dict(tuple(ctx["stress"]["daily"].groupby("fonKodu")))
    event = ctx["stress"]["event_date"]
    nearest = similar_funds(ctx["universe"])
    fund_count = len(universe)

    for code, base in stressed.iterrows():
        row = universe.loc[code].to_dict() if code in universe.index else None
        yield code, {
            "code": code,
            "name": base["fonUnvan"],
            "founder": base["founder"],
            "founder_slug": slugify(base["founder"]),
            "row": row,
            "base": base.to_dict(),
            "summary": fund_summary(row, ctx["info"], ctx["first_day"], ctx["last_day"], fund_count) if row else [],
            "similar": nearest.get(code, []),
            "flow_chart": daily_flow_chart(daily[code], event) if code in daily else "",
            "event": event,
        }


def founder_contexts(universes):
    """Every founder with its funds, across both universes, largest first."""
    founders = {}
    for ctx in universes:
        universe = ctx["universe"].set_index("fonKodu", drop=False)
        for base in ctx["stress"]["funds"].to_dict("records"):
            entry = founders.setdefault(
                base["founder"],
                {"name": base["founder"], "slug": slugify(base["founder"]), "funds": [], "universes": []},
            )
            row = universe.loc[base["fonKodu"]].to_dict() if base["fonKodu"] in universe.index else {}
            entry["funds"].append({**base, **row, "analysed": bool(row)})
            if ctx["info"]["name"] not in entry["universes"]:
                entry["universes"].append(ctx["info"]["name"])

    for entry in founders.values():
        funds = entry["funds"]
        analysed = [f for f in funds if f["analysed"]]
        start_aum = sum(f["start_aum"] for f in analysed)
        entry.update(
            fund_count=len(funds),
            analysed_count=len(analysed),
            # Every fund's size at the start, analysed or not: a founder whose
            # funds stopped being valued shows it in the gap between the two
            start_aum_all=sum(f["start_aum"] for f in funds if pd.notna(f["start_aum"])),
            end_aum=sum(f["end_aum"] for f in analysed),
            net_flow=sum(f["total_net_flow"] for f in analysed),
            market_effect=sum(f["total_market_effect"] for f in analysed),
            flow_pct=sum(f["total_net_flow"] for f in analysed) / start_aum if start_aum else None,
            frozen=sum(bool(f["frozen"]) for f in funds),
            unpublished=sum(bool(f["unpublished"]) for f in funds),
        )
        funds.sort(key=lambda f: f.get("end_aum") or 0, reverse=True)
    return sorted(founders.values(), key=lambda e: e["end_aum"], reverse=True)


def build(out: Path, base_url: str, end=None, cache_dir: Path | None = None) -> None:
    end = (
        pd.Timestamp(end).normalize()
        if end
        else pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    )
    start = end - pd.DateOffset(months=1)

    analyses = [analyse(fund_type, start, end, cache_dir) for fund_type in UNIVERSES]

    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(money=money, pct=pct, count=count, day=day, slug=slugify)
    env.tests["present"] = lambda value: value is not None and not pd.isna(value)
    env.globals["breadcrumb_items"] = breadcrumb_items
    common = {
        "base_url": base_url,
        "app_url": APP_URL,
        "repo_url": REPO_URL,
        "built": pd.Timestamp.now(tz="Europe/Istanbul"),
        "start": start,
        "end": end,
        "freeze_days": FREEZE_MIN_DAYS,
        "turn_pct": round(TURN_THRESHOLD * 100),
        "drop_pct": round(abs(PRICE_DROP) * 100),
        "outflow_pct": round(abs(HEAVY_OUTFLOW) * 100),
        "min_aum": money(UNIVERSE_MIN_START_AUM),
        "flow_list_length": FLOW_LIST_LENGTH,
    }

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(HERE / "static", out / "static")
    (out / ".nojekyll").write_text("")

    # Ownership files the search engines ask for (Google, Bing, Yandex, IndexNow)
    # are served from the top of the site as they are.
    verification = HERE / "verification"
    if verification.is_dir():
        for file in verification.iterdir():
            if file.is_file() and file.name != "README.md":
                shutil.copy(file, out / file.name)

    pages = [""]

    def write(path, template, **context):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Links are relative, so the same files work from disk and on Pages
        root = "../" * path.count("/")
        html = env.get_template(template).render(**common, **context, root=root, path=path)
        target.write_text(html, encoding="utf-8")
        if path != "index.html":
            pages.append(path)

    universes = [universe_context(a) for a in analyses]
    founders = founder_contexts(universes)
    any_stopped = any(u["frozen"] or u["unpublished"] for u in universes)

    write("index.html", "index.html", universes=universes, any_stopped=any_stopped)
    write("kurucular.html", "founders.html", founders=founders)
    if any_stopped:
        write("alim-satimi-duran-fonlar.html", "stopped.html", universes=universes)

    search_index = []
    for ctx in universes:
        slug = ctx["info"]["slug"]
        write(f"{slug}.html", "universe.html", u=ctx, any_stopped=any_stopped)
        write(
            f"{slug}-para-akisi.html",
            "flows.html",
            u=ctx,
            inflows=fund_rows(ctx, sort="total_net_flow", ascending=False, limit=FLOW_LIST_LENGTH),
            outflows=fund_rows(ctx, sort="total_net_flow", ascending=True, limit=FLOW_LIST_LENGTH),
            any_stopped=any_stopped,
        )
        for code, fund in fund_contexts(ctx):
            write(f"fon/{code}.html", "fund.html", u=ctx, f=fund)
            search_index.append({"c": code, "n": fund["name"], "u": ctx["info"]["short"]})

    for founder in founders:
        write(f"kurucu/{founder['slug']}.html", "founder.html", k=founder)

    (out / "fonlar.json").write_text(
        json.dumps(sorted(search_index, key=lambda r: r["c"]), ensure_ascii=False), encoding="utf-8"
    )
    lastmod = end.strftime("%Y-%m-%d")
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{base_url}{p}</loc><lastmod>{lastmod}</lastmod></url>\n" for p in pages)
        + "</urlset>\n",
        encoding="utf-8",
    )
    # Crawlers only read robots.txt at the top of a host, which for a project
    # site is not this folder; the copy here is for a custom domain, and the
    # sitemap is handed to the search engines directly.
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}sitemap.xml\n")
    print(f"Wrote {len(pages)} pages to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the turkeyFundLens static site.")
    parser.add_argument("--out", default="_site", type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--end", default=None, help="Last day of the window; today in Istanbul by default")
    parser.add_argument(
        "--cache-dir",
        default=None,
        type=Path,
        help="Keep fetched frames here and reuse them, for working on the templates",
    )
    args = parser.parse_args()
    build(args.out, args.base_url, args.end, args.cache_dir)


if __name__ == "__main__":
    main()
