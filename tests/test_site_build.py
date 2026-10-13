"""
The public site must not be built from data with a month missing: the first
build on GitHub lost the baseline month to TEFAS timeouts and published "no
stress event" for a window that had one. These pin down that a missing month
stops the build, and that only today's not-yet-published day may be absent.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("jinja2")

SPEC = importlib.util.spec_from_file_location(
    "site_build", Path(__file__).resolve().parents[1] / "site" / "build.py"
)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def fake_period(missing):
    """A fetch_tefas_period that returns nothing for chunks starting on a missing day."""
    def fetch(chunk_start, chunk_end, config=None, verbose=True):
        if pd.Timestamp(chunk_start) in missing:
            return pd.DataFrame(), pd.DataFrame()
        row = {"fonKodu": "AAA", "fonUnvan": "A", "tarih": str(pd.Timestamp(chunk_start).date())}
        return pd.DataFrame([row]), pd.DataFrame([row])
    return fetch


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(build, "CHUNK_PAUSE_SECONDS", 0)
    monkeypatch.setattr(build.time, "sleep", lambda seconds: None)


def test_a_month_that_never_arrives_stops_the_build(monkeypatch):
    monkeypatch.setattr(build, "fetch_tefas_period", fake_period({pd.Timestamp("2026-08-12")}))
    with pytest.raises(RuntimeError, match="not building from a partial month"):
        build.fetch_strict("YAT", pd.Timestamp("2026-08-12"), pd.Timestamp("2026-10-12"))


def test_a_month_that_arrives_on_a_later_round_is_used(monkeypatch):
    calls = {"n": 0}
    good = fake_period(set())

    def flaky(chunk_start, chunk_end, config=None, verbose=True):
        calls["n"] += 1
        if calls["n"] == 1:
            return pd.DataFrame(), pd.DataFrame()
        return good(chunk_start, chunk_end)

    monkeypatch.setattr(build, "fetch_tefas_period", flaky)
    general, _ = build.fetch_strict("YAT", pd.Timestamp("2026-08-12"), pd.Timestamp("2026-10-12"))
    assert len(general) == 3


def test_today_not_yet_published_is_allowed(monkeypatch):
    today = pd.Timestamp("2026-10-12")
    monkeypatch.setattr(build, "fetch_tefas_period", fake_period({today}))
    general, _ = build.fetch_strict("YAT", pd.Timestamp("2026-08-12"), today)
    assert len(general) == 2


def test_today_is_asked_again_before_it_is_given_up(monkeypatch):
    """A timeout and an unpublished day both come back empty; retry first."""
    today = pd.Timestamp("2026-10-12")
    good = fake_period(set())
    asked = {"today": 0}

    def flaky_today(chunk_start, chunk_end, config=None, verbose=True):
        if pd.Timestamp(chunk_start) == today:
            asked["today"] += 1
            if asked["today"] == 1:
                return pd.DataFrame(), pd.DataFrame()
        return good(chunk_start, chunk_end)

    monkeypatch.setattr(build, "fetch_tefas_period", flaky_today)
    general, _ = build.fetch_strict("YAT", pd.Timestamp("2026-08-12"), today)
    assert asked["today"] == 2
    assert len(general) == 3


# ------------------------------------------------------------------ pages


def test_a_founder_name_becomes_a_plain_address():
    assert build.slugify("İŞ PORTFÖY") == "is-portfoy"
    assert build.slugify("HDI FİBA EMEKLİLİK VE HAYAT") == "hdi-fiba-emeklilik-ve-hayat"
    assert build.slugify("A1 CAPİTAL PORTFÖY") == "a1-capital-portfoy"


def test_numbers_are_written_the_turkish_way():
    assert build.pct(0.1234) == "%12,34"
    assert build.pct(-0.05) == "-%5,00"
    assert build.money(2_710_000_000) == "2,71 milyar TL"
    assert build.count(1968) == "1.968"


def summary_row(**changes):
    row = {
        "fonKodu": "AAA", "cumulative_return": -0.2662, "start_aum": 2.71e9, "end_aum": 1.55e9,
        "aum_change_pct": -0.4276, "market_effect_pct": -0.2293, "flow_pct": -0.1983,
        "total_net_flow": -537.32e6, "participant_change": -1548, "end_participants": 9924,
        "peer_count": 104, "return_rank": 104.0, "flow_rank": 87.0, "aum_rank": 502.0,
        "archetype": "Fon Sepeti Ağırlıklı Fon",
    }
    return {**row, **changes}


def fund_summary(row):
    info = {"holders": "Yatırımcı"}
    return " ".join(
        build.fund_summary(row, info, pd.Timestamp("2026-09-14"), pd.Timestamp("2026-10-13"), 1966)
    )


def test_the_summary_says_what_happened_to_this_fund():
    text = fund_summary(summary_row())
    assert "AAA, 14 Eylül 2026 – 13 Ekim 2026 arasında %26,62 değer kaybetti." in text
    assert "Yatırımcı sayısı 9.924; dönem içinde 1.548 azaldı." in text
    assert "104 fon (Fon Sepeti Ağırlıklı Fon) arasında getiride 104., yatırımcı akışında 87. sırada." in text


def test_the_summary_follows_the_sign_of_the_numbers():
    text = fund_summary(summary_row(cumulative_return=0.031, participant_change=12))
    assert "%3,10 değer kazandı" in text
    assert "12 arttı" in text
    assert "değişmedi" in fund_summary(summary_row(participant_change=0))


def test_a_fund_with_too_few_peers_is_not_ranked_among_them():
    assert "arasında getiride" not in fund_summary(summary_row(peer_count=2))


# ------------------------------------------------------------------ charts


def test_charts_are_plain_svg_with_the_event_marked():
    days = pd.bdate_range("2026-09-14", periods=5)
    svg = build.bar_chart(days, [19.0, 7.5, -1.6, -30.6, 4.8], event=days[3])
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.count('class="pos"') == 3 and svg.count('class="neg"') == 2
    assert svg.count('class="ev"') == 1
    assert "17.09.2026: %−30,60" in svg
    assert "<script" not in svg


def test_a_chart_with_no_event_draws_no_event_line():
    days = pd.bdate_range("2026-09-14", periods=3)
    assert 'class="ev"' not in build.bar_chart(days, [1.0, 2.0, 3.0])
    assert build.bar_chart([], []) == ""
