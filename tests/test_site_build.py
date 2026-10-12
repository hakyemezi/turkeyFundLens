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
pytest.importorskip("altair")

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
