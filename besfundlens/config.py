from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "besfundlens.sqlite"

URL_GENEL = "https://fonturkey.com.tr/api/funds/fonGnlBlgSiraliGetirDosya"
URL_DAGILIM = "https://fonturkey.com.tr/api/funds/dagilimSiraliGetirDosya"

# TEFAS fund types, as its fonTipi field names them. EMK is the pension (BES)
# universe the project started with; YAT is the securities investment funds tab
# (Menkul Kıymet Yatırım Fonları). Both are published through the same two
# endpoints with the same allocation codes, so the engine takes either as is.
FUND_TYPE_PENSION = "EMK"
FUND_TYPE_SECURITIES = "YAT"
FUND_TYPES = (FUND_TYPE_PENSION, FUND_TYPE_SECURITIES)

DEFAULT_FON_TIPI = FUND_TYPE_PENSION
DEFAULT_LANGUAGE = "en"

# One cache per fund type. fetch_history.py replaces the tables it writes, so a
# shared file would let fetching one universe silently wipe out the other.
DEFAULT_DB_PATHS = {
    FUND_TYPE_PENSION: DEFAULT_DB_PATH,
    FUND_TYPE_SECURITIES: DEFAULT_DATA_DIR / "besfundlens_yat.sqlite",
}
