from __future__ import annotations

from typing import Optional, Union, Sequence

import numpy as np
import pandas as pd

from besfundlens.core.utils import (  # noqa: F401  (re-exported for backward compatibility)
    DEFAULT_LANGUAGE,
    LOOKBACK_PRESETS,
    SUPPORTED_LANGUAGES,
    format_number,
    format_pct,
    format_try,
    is_finite_number,
    make_safe_col_name,
    normalize_fund_codes,
    normalize_language,
    parse_tarih,
    resolve_lookback_intervals,
    safe_divide,
    safe_divide_series,
)
from besfundlens.core.asset_metadata import (  # noqa: F401  (re-exported for backward compatibility)
    add_dna_columns,
    asset_group_map,
    asset_name_en,
    asset_name_tr,
    broad_asset_group_map,
    build_asset_metadata,
    build_dna_panel,
    clean_dna_label,
    currency_exposure_map,
    market_scope_map,
    validate_asset_metadata,
)
from besfundlens.classification.config import (
    DEFAULT_CONFIG as DEFAULT_CLASSIFICATION_CONFIG,
)
from besfundlens.classification.pipeline import classify_universe
from besfundlens.classification.report import (
    build_classification_sections,
    classification_note_lines,
)
from besfundlens.classification.taxonomy import GROUP_LABELS_TR

pd.set_option('display.expand_frame_repr', False)

# ============================================================
# 1. Configuration
# ============================================================

SHOW_STARTUP_DIAGNOSTICS = False
UNIVERSE_MIN_START_AUM = 1_000_000
BUILD_VERSION = "2026-08-10-repo-stable-v2-classification"


# ============================================================
# 2. Utility Functions
# ============================================================
#
# The generic helpers below now live in `besfundlens.core.utils` and the asset
# metadata / DNA aggregation layer lives in `besfundlens.core.asset_metadata`.
# They are re-exported here so that existing imports such as
# `from besfundlens.core.engine import safe_divide` keep working.


def print_build_info():
    """
    Çalışan dosyanın güncel sürümünü ve temel universe kalite eşiğini gösterir.
    Eski fonksiyonların cache'ten çalışıp çalışmadığını kontrol etmek için kullanılır.
    """
    print(f"besFundLens build version: {BUILD_VERSION}")
    print(f"Universe min start AUM: {UNIVERSE_MIN_START_AUM:,.0f} TL")


# ============================================================
# 3. Data Cleaning and Main Panel
# ============================================================

def prepare_main_panel(
    df_genel: pd.DataFrame,
    df_dagilim: pd.DataFrame,
    verbose: bool = False,
):
    """
    df_genel ve df_dagilim tablolarını temizleyip fonKodu + tarih bazlı ana panel oluşturur.

    Not:
    - DB okuma kısmına dokunmuyoruz.
    - Bu fonksiyon DB'den okunan df_genel ve df_dagilim üzerinde çalışır.
    """
    df_genel_clean = df_genel.copy()
    df_dagilim_clean = df_dagilim.copy()

    df_genel_clean["tarih"] = parse_tarih(df_genel_clean["tarih"])
    df_dagilim_clean["tarih"] = parse_tarih(df_dagilim_clean["tarih"])

    df_genel_clean = df_genel_clean.dropna(axis=1, how="all")
    df_dagilim_clean = df_dagilim_clean.dropna(axis=1, how="all")

    id_cols = ["fonKodu", "fonUnvan", "tarih"]

    asset_cols = [
        col for col in df_dagilim_clean.columns
        if col not in id_cols
    ]

    for col in asset_cols:
        df_dagilim_clean[col] = pd.to_numeric(
            df_dagilim_clean[col],
            errors="coerce",
        )

    df_dagilim_clean[asset_cols] = df_dagilim_clean[asset_cols].fillna(0)

    df_dagilim_clean["dagilim_toplam"] = df_dagilim_clean[asset_cols].sum(axis=1)

    genel_dup_count = df_genel_clean.duplicated(
        subset=["fonKodu", "tarih"]
    ).sum()

    dagilim_dup_count = df_dagilim_clean.duplicated(
        subset=["fonKodu", "tarih"]
    ).sum()

    df_panel = df_genel_clean.merge(
        df_dagilim_clean.drop(columns=["fonUnvan"], errors="ignore"),
        on=["fonKodu", "tarih"],
        how="left",
    )

    # Dağılım kolonlarında merge sonrası boş kalan değerleri 0 yapıyoruz.
    # dagilim_toplam alanını ise NaN bırakıyoruz; böylece dağılım verisi olmayan
    # fon-tarih satırlarını ayırt edebiliriz.
    df_panel[asset_cols] = df_panel[asset_cols].fillna(0)

    df_panel = (
        df_panel
        .sort_values(["fonKodu", "tarih"])
        .reset_index(drop=True)
    )

    diagnostics = {
        "df_genel_clean_shape": df_genel_clean.shape,
        "df_dagilim_clean_shape": df_dagilim_clean.shape,
        "df_panel_shape": df_panel.shape,
        "asset_col_count": len(asset_cols),
        "genel_dup_count": genel_dup_count,
        "dagilim_dup_count": dagilim_dup_count,
        "dagilim_outside_90_105_count": df_dagilim_clean[
            ~df_dagilim_clean["dagilim_toplam"].between(90, 105)
        ].shape[0],
        "df_genel_nat_tarih_count": df_genel_clean["tarih"].isna().sum(),
        "df_dagilim_nat_tarih_count": df_dagilim_clean["tarih"].isna().sum(),
        "df_panel_nat_tarih_count": df_panel["tarih"].isna().sum(),
    }

    if verbose:
        print("Main panel diagnostics:")
        for key, value in diagnostics.items():
            print(f"- {key}: {value}")

    return df_panel, df_genel_clean, df_dagilim_clean, asset_cols, diagnostics


# ============================================================
# 4. Asset Metadata  -> besfundlens/core/asset_metadata.py
# 5. DNA Feature Engineering -> besfundlens/core/asset_metadata.py
# ============================================================


# ============================================================
# 6. Flow Feature Engineering
# ============================================================

def add_flow_features(panel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fon fiyatı, portföy büyüklüğü, tedavüldeki pay sayısı ve katılımcı sayısı üzerinden
    zaman serisi ve tahmini net akış değişkenlerini üretir.

    Önemli not:
    - Fon fiyatı = portföyBuyukluk / tedPaySayisi
    - Yayınlanan fon fiyatı 6 ondalık basamakla geldiği için fiyat kontrolü ayrı tutulur.
    - Oran hesaplarında sıfır payda durumları güvenli şekilde NaN'a çevrilir.
    """
    result_df = (
        panel_df
        .sort_values(["fonKodu", "tarih"])
        .reset_index(drop=True)
        .copy()
    )

    # Fon fiyatı = Portföy büyüklüğü / Tedavüldeki pay sayısı
    # Yayınlanan fiyat 6 ondalık basamakla geldiği için kontrolü ayrıca tutuyoruz.
    result_df["calculated_fiyat_raw"] = safe_divide_series(
        result_df["portfoyBuyukluk"],
        result_df["tedPaySayisi"],
    )

    result_df["calculated_fiyat_6"] = result_df["calculated_fiyat_raw"].round(6)

    result_df["fiyat_abs_diff"] = (
        result_df["fiyat"] - result_df["calculated_fiyat_6"]
    )

    result_df["fiyat_diff_pct"] = safe_divide_series(
        result_df["fiyat_abs_diff"],
        result_df["fiyat"],
    ) * 100

    grouped = result_df.groupby("fonKodu", group_keys=False)

    result_df["prev_tarih"] = grouped["tarih"].shift(1)
    result_df["prev_fiyat"] = grouped["fiyat"].shift(1)
    result_df["prev_portfoyBuyukluk"] = grouped["portfoyBuyukluk"].shift(1)
    result_df["prev_kisiSayisi"] = grouped["kisiSayisi"].shift(1)
    result_df["prev_tedPaySayisi"] = grouped["tedPaySayisi"].shift(1)

    result_df["days_since_prev"] = (
        result_df["tarih"] - result_df["prev_tarih"]
    ).dt.days

    result_df["fund_return"] = (
        safe_divide_series(result_df["fiyat"], result_df["prev_fiyat"]) - 1
    )

    result_df["aum_change"] = (
        result_df["portfoyBuyukluk"] - result_df["prev_portfoyBuyukluk"]
    )

    result_df["aum_change_pct"] = (
        safe_divide_series(
            result_df["portfoyBuyukluk"],
            result_df["prev_portfoyBuyukluk"],
        ) - 1
    )

    result_df["participant_change"] = (
        result_df["kisiSayisi"] - result_df["prev_kisiSayisi"]
    )

    result_df["participant_change_pct"] = (
        safe_divide_series(
            result_df["kisiSayisi"],
            result_df["prev_kisiSayisi"],
        ) - 1
    )

    result_df["unit_change"] = (
        result_df["tedPaySayisi"] - result_df["prev_tedPaySayisi"]
    )

    result_df["unit_change_pct"] = (
        safe_divide_series(
            result_df["tedPaySayisi"],
            result_df["prev_tedPaySayisi"],
        ) - 1
    )

    result_df["estimated_net_flow_aum_method"] = (
        result_df["portfoyBuyukluk"]
        - result_df["prev_portfoyBuyukluk"] * (1 + result_df["fund_return"])
    )

    result_df["estimated_net_flow_aum_method_pct"] = safe_divide_series(
        result_df["estimated_net_flow_aum_method"],
        result_df["prev_portfoyBuyukluk"],
    )

    # Ana akış ölçütü: Tedavüldeki pay sayısı değişimi × yayınlanan fiyat
    result_df["estimated_net_flow_unit_method"] = (
        result_df["unit_change"] * result_df["fiyat"]
    )

    result_df["estimated_net_flow_unit_method_pct"] = safe_divide_series(
        result_df["estimated_net_flow_unit_method"],
        result_df["prev_portfoyBuyukluk"],
    )

    result_df["estimated_net_flow_diff"] = (
        result_df["estimated_net_flow_aum_method"]
        - result_df["estimated_net_flow_unit_method"]
    )

    result_df["estimated_net_flow_diff_pct"] = safe_divide_series(
        result_df["estimated_net_flow_diff"],
        result_df["prev_portfoyBuyukluk"],
    )

    result_df["estimated_net_flow_per_participant"] = safe_divide_series(
        result_df["estimated_net_flow_unit_method"],
        result_df["prev_kisiSayisi"],
    )

    return result_df


# ============================================================
# 7. DNA Snapshot Functions
# ============================================================

def build_dna_table(
    row: pd.Series,
    dna_cols: list,
    prefix: str,
    min_weight: float = 0.01,
    top_n: Optional[int] = None,
) -> pd.DataFrame:
    """
    Tek bir fon-tarih satırındaki DNA kolonlarını okunabilir tabloya çevirir.
    """
    records = []

    for col in dna_cols:
        weight = row[col]

        if pd.isna(weight):
            continue

        if abs(weight) < min_weight:
            continue

        records.append({
            "group": clean_dna_label(col, prefix),
            "weight": weight,
        })

    result = pd.DataFrame(records)

    if result.empty:
        return result

    result = result.sort_values("weight", ascending=False)

    if top_n is not None:
        result = result.head(top_n)

    return result.reset_index(drop=True)


def get_top_group(dna_table: pd.DataFrame):
    """
    DNA tablosundaki en büyük ağırlıklı grubu döndürür.
    """
    if dna_table is None or dna_table.empty:
        return None, 0

    top_row = dna_table.iloc[0]
    return top_row["group"], top_row["weight"]


def interpret_dna_snapshot(
    broad_table: pd.DataFrame,
    scope_table: pd.DataFrame,
    currency_table: pd.DataFrame,
) -> list:
    """
    Fund DNA tablolarından basit ve okunabilir yorum üretir.
    """
    top_asset_group, top_asset_weight = get_top_group(broad_table)
    top_scope_group, top_scope_weight = get_top_group(scope_table)
    top_currency_group, top_currency_weight = get_top_group(currency_table)

    comments = []

    if top_asset_group is not None:
        comments.append(
            f"The fund is mainly exposed to {top_asset_group} "
            f"with a weight of {top_asset_weight:.2f}%."
        )

    if top_scope_group is not None:
        comments.append(
            f"From a market-scope perspective, the dominant exposure is "
            f"{top_scope_group} at {top_scope_weight:.2f}%."
        )

    if top_currency_group is not None:
        comments.append(
            f"From a currency-risk perspective, the dominant exposure is "
            f"{top_currency_group} at {top_currency_weight:.2f}%."
        )

    lookthrough_weight = 0

    if scope_table is not None and not scope_table.empty:
        matched = scope_table.loc[
            scope_table["group"].eq("Look-through Required"),
            "weight",
        ]

        if not matched.empty:
            lookthrough_weight = matched.iloc[0]

    if lookthrough_weight >= 10:
        comments.append(
            f"The fund has a meaningful look-through component "
            f"of {lookthrough_weight:.2f}%, which should be analyzed in more detail."
        )
    elif lookthrough_weight > 0:
        comments.append(
            f"The fund has a small look-through component of "
            f"{lookthrough_weight:.2f}%."
        )

    return comments


def fund_dna_snapshot(
    fund_code: str,
    panel_df: Optional[pd.DataFrame] = None,
    top_n: int = 10,
    verbose: bool = True,
):
    """
    Seçilen fonun en güncel Fund DNA özetini üretir.
    """
    if panel_df is None:
        panel_df = df_panel_dna

    fund_code = fund_code.upper()

    fund_data = panel_df.loc[
        panel_df["fonKodu"].eq(fund_code)
    ].copy()

    if fund_data.empty:
        if verbose:
            print(f"{fund_code} kodlu fon bulunamadı.")
        return None

    # DNA için dağılım verisi olan son satırı tercih ediyoruz.
    valid_dna_data = fund_data[
        fund_data["dagilim_toplam"].notna()
    ].copy()

    if valid_dna_data.empty:
        latest_row = fund_data.sort_values("tarih").iloc[-1]
    else:
        latest_row = valid_dna_data.sort_values("tarih").iloc[-1]

    broad_table = build_dna_table(
        row=latest_row,
        dna_cols=dna_broad_cols,
        prefix="dna_broad",
        min_weight=0.01,
        top_n=top_n,
    )

    scope_table = build_dna_table(
        row=latest_row,
        dna_cols=dna_scope_cols,
        prefix="dna_scope",
        min_weight=0.01,
        top_n=None,
    )

    currency_table = build_dna_table(
        row=latest_row,
        dna_cols=dna_currency_cols,
        prefix="dna_currency",
        min_weight=0.01,
        top_n=None,
    )

    comments = interpret_dna_snapshot(
        broad_table=broad_table,
        scope_table=scope_table,
        currency_table=currency_table,
    )

    if verbose:
        print("=" * 80)
        print(f"Fund DNA Snapshot: {fund_code}")
        print("=" * 80)
        print(f"Fund Name        : {latest_row['fonUnvan']}")
        print(f"Date             : {latest_row['tarih'].date()}")
        print(f"Price            : {latest_row['fiyat']:.6f}")
        print(f"Participants     : {latest_row['kisiSayisi']:,}")
        print(f"Portfolio Size   : {latest_row['portfoyBuyukluk']:,.2f}")
        print(f"Distribution Sum : {latest_row['dagilim_toplam']:.2f}")
        print("-" * 80)

        print("\nMain Asset DNA:")
        print(broad_table)

        print("\nMarket Scope DNA:")
        print(scope_table)

        print("\nCurrency Exposure DNA:")
        print(currency_table)

        print("\nInterpretation:")
        for comment in comments:
            print(f"- {comment}")

    return {
        "fund_code": fund_code,
        "latest_row": latest_row,
        "broad_table": broad_table,
        "scope_table": scope_table,
        "currency_table": currency_table,
        "comments": comments,
    }


# ============================================================
# 8. Flow Snapshot Functions
# ============================================================

def classify_flow_magnitude(flow_pct) -> str:
    """
    Net flow'un başlangıç AUM'a oranına göre ekonomik anlamlılık sınıflandırması.
    flow_pct decimal formatta beklenir.

    Örnek:
    0.0082 -> 0.82%
    """
    if pd.isna(flow_pct):
        return "Unknown"

    abs_flow = abs(flow_pct)

    if abs_flow < 0.0005:
        return "Neutral / negligible"
    elif abs_flow < 0.0025:
        return "Small"
    elif abs_flow < 0.01:
        return "Moderate"
    else:
        return "Strong"


def classify_market_effect_magnitude(market_pct) -> str:
    """
    Market effect'in başlangıç AUM'a oranına göre büyüklüğünü sınıflandırır.
    """
    if pd.isna(market_pct):
        return "Unknown"

    abs_effect = abs(market_pct)

    if abs_effect < 0.0005:
        return "Neutral / negligible"
    elif abs_effect < 0.0025:
        return "Small"
    elif abs_effect < 0.01:
        return "Moderate"
    else:
        return "Strong"


def classify_flow_direction(flow_pct, threshold: float = 0.0005) -> str:
    """
    Net flow yönünü ekonomik anlamlılık eşiğiyle sınıflandırır.
    """
    if pd.isna(flow_pct):
        return "Unknown"

    if flow_pct > threshold:
        return "Positive"
    elif flow_pct < -threshold:
        return "Negative"
    else:
        return "Neutral"


def classify_flow_regime_v2(flow_pct, participant_change) -> str:
    """
    Net flow'un ekonomik anlamlılığına ve katılımcı değişimine göre rejim sınıflandırması.
    """
    flow_direction = classify_flow_direction(flow_pct)
    flow_magnitude = classify_flow_magnitude(flow_pct)

    if flow_direction == "Neutral":
        if participant_change > 0:
            return "Neutral flow with participant growth"
        elif participant_change < 0:
            return "Neutral flow with participant decline"
        else:
            return "Neutral flow regime"

    if flow_direction == "Positive":
        if participant_change > 0:
            return f"{flow_magnitude} net inflow with participant growth"
        elif participant_change < 0:
            return f"{flow_magnitude} net inflow without participant growth"
        else:
            return f"{flow_magnitude} net inflow with stable participant count"

    if flow_direction == "Negative":
        if participant_change < 0:
            return f"{flow_magnitude} net outflow with participant decline"
        elif participant_change > 0:
            return f"{flow_magnitude} net outflow despite participant growth"
        else:
            return f"{flow_magnitude} net outflow with stable participant count"

    return "Unknown flow regime"


def fund_flow_snapshot(
    fund_code: str,
    panel_df: Optional[pd.DataFrame] = None,
    lookback_intervals: int = 20,
    lookback: Optional[Union[str, int]] = None,
    verbose: bool = True,
):
    """
    Seçilen fon için son N zaman aralığına göre akış ve büyüme özeti üretir.

    lookback_intervals:
        Kaç dönemlik değişim incelenecek.
        Örneğin 20 dersek, 21 gözlem alınır ve 20 aralık analiz edilir.
    """
    if panel_df is None:
        panel_df = df_panel_dna

    lookback_intervals = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    fund_code = fund_code.upper()

    fund_data = panel_df.loc[
        panel_df["fonKodu"].eq(fund_code)
    ].copy()

    if fund_data.empty:
        if verbose:
            print(f"{fund_code} kodlu fon bulunamadı.")
        return None

    fund_data = fund_data.sort_values("tarih").reset_index(drop=True)

    needed_observations = lookback_intervals + 1

    if fund_data.shape[0] < needed_observations:
        if verbose:
            print(f"{fund_code} için yeterli zaman serisi yok.")
        return None

    recent = fund_data.tail(needed_observations).copy()

    first_row = recent.iloc[0]
    latest_row = recent.iloc[-1]

    # İlk satır başlangıç noktasıdır.
    # Akış ve günlük getiri toplamları sadece sonraki satırlardan alınır.
    flow_period = recent.iloc[1:].copy()

    cumulative_return = safe_divide(
        latest_row["fiyat"],
        first_row["fiyat"],
    ) - 1

    total_aum_change = (
        latest_row["portfoyBuyukluk"] - first_row["portfoyBuyukluk"]
    )

    total_aum_change_pct = safe_divide(
        latest_row["portfoyBuyukluk"],
        first_row["portfoyBuyukluk"],
    ) - 1

    total_market_effect = (
        flow_period["prev_portfoyBuyukluk"] * flow_period["fund_return"]
    ).sum()

    total_net_flow_unit = flow_period["estimated_net_flow_unit_method"].sum()
    total_net_flow_aum = flow_period["estimated_net_flow_aum_method"].sum()

    total_flow_diff = total_net_flow_aum - total_net_flow_unit

    total_participant_change = (
        latest_row["kisiSayisi"] - first_row["kisiSayisi"]
    )

    total_participant_change_pct = safe_divide(
        latest_row["kisiSayisi"],
        first_row["kisiSayisi"],
    ) - 1

    avg_daily_flow = safe_divide(
        total_net_flow_unit,
        flow_period.shape[0],
    )

    period_flow_per_start_participant = safe_divide(
        total_net_flow_unit,
        first_row["kisiSayisi"],
    )

    avg_daily_flow_per_participant = (
        flow_period["estimated_net_flow_per_participant"].mean()
    )

    flow_pct_start_aum = safe_divide(
        total_net_flow_unit,
        first_row["portfoyBuyukluk"],
    )

    market_effect_pct_start_aum = safe_divide(
        total_market_effect,
        first_row["portfoyBuyukluk"],
    )

    regime = classify_flow_regime_v2(
        flow_pct=flow_pct_start_aum,
        participant_change=total_participant_change,
    )

    if verbose:
        print("=" * 80)
        print(f"Fund Flow Snapshot: {fund_code}")
        print("=" * 80)
        print(f"Fund Name              : {latest_row['fonUnvan']}")
        print(f"Period                 : {first_row['tarih'].date()} → {latest_row['tarih'].date()}")
        print(f"Intervals              : {flow_period.shape[0]}")
        print("-" * 80)

        print(f"Start Price            : {first_row['fiyat']:.6f}")
        print(f"End Price              : {latest_row['fiyat']:.6f}")
        print(f"Cumulative Return      : {format_pct(cumulative_return)}")
        print("-" * 80)

        print(f"Start AUM              : {format_try(first_row['portfoyBuyukluk'])}")
        print(f"End AUM                : {format_try(latest_row['portfoyBuyukluk'])}")
        print(f"AUM Change             : {format_try(total_aum_change)}")
        print(f"AUM Change %           : {format_pct(total_aum_change_pct)}")
        print("-" * 80)

        print(f"Market Effect          : {format_try(total_market_effect)}")
        print(f"Market Effect %        : {format_pct(market_effect_pct_start_aum)}")
        print(f"Net Flow - Unit Method : {format_try(total_net_flow_unit)}")
        print(f"Net Flow %             : {format_pct(flow_pct_start_aum)}")
        print(f"Net Flow - AUM Method  : {format_try(total_net_flow_aum)}")
        print(f"Flow Method Diff       : {format_try(total_flow_diff)}")
        print("-" * 80)

        print(f"Start Participants     : {first_row['kisiSayisi']:,}")
        print(f"End Participants       : {latest_row['kisiSayisi']:,}")
        print(f"Participant Change     : {total_participant_change:,.0f}")
        print(f"Participant Change %   : {format_pct(total_participant_change_pct)}")
        print(f"Avg Daily Flow         : {format_try(avg_daily_flow)}")
        print(f"Flow / Start Participant: {format_try(period_flow_per_start_participant)}")
        print(f"Avg Daily Flow / Participant: {format_try(avg_daily_flow_per_participant)}")
        print("-" * 80)

        print(f"Flow Regime            : {regime}")

    return {
        "fund_code": fund_code,
        "recent_data": recent,
        "flow_period": flow_period,
        "start_date": first_row["tarih"],
        "end_date": latest_row["tarih"],
        "intervals": flow_period.shape[0],
        "start_aum": first_row["portfoyBuyukluk"],
        "end_aum": latest_row["portfoyBuyukluk"],
        "start_participants": first_row["kisiSayisi"],
        "end_participants": latest_row["kisiSayisi"],
        "cumulative_return": cumulative_return,
        "total_aum_change": total_aum_change,
        "total_aum_change_pct": total_aum_change_pct,
        "total_market_effect": total_market_effect,
        "market_effect_pct_start_aum": market_effect_pct_start_aum,
        "total_net_flow_unit": total_net_flow_unit,
        "total_net_flow_aum": total_net_flow_aum,
        "flow_pct_start_aum": flow_pct_start_aum,
        "total_flow_diff": total_flow_diff,
        "total_participant_change": total_participant_change,
        "total_participant_change_pct": total_participant_change_pct,
        "avg_daily_flow": avg_daily_flow,
        "period_flow_per_start_participant": period_flow_per_start_participant,
        "avg_daily_flow_per_participant": avg_daily_flow_per_participant,
        "flow_regime": regime,
    }


def interpret_flow_snapshot_v2(flow_snapshot: dict) -> list:
    """
    Materiality-aware flow interpretation.
    Net flow'un sadece yönüne değil, ekonomik büyüklüğüne de bakar.
    """
    if flow_snapshot is None:
        return []

    fund_code = flow_snapshot["fund_code"]
    cumulative_return = flow_snapshot["cumulative_return"]
    total_aum_change = flow_snapshot["total_aum_change"]
    total_net_flow = flow_snapshot["total_net_flow_unit"]
    total_market_effect = flow_snapshot["total_market_effect"]
    participant_change = flow_snapshot["total_participant_change"]
    flow_pct = flow_snapshot["flow_pct_start_aum"]
    market_pct = flow_snapshot["market_effect_pct_start_aum"]
    flow_diff = flow_snapshot["total_flow_diff"]
    regime = flow_snapshot["flow_regime"]

    flow_direction = classify_flow_direction(flow_pct)
    flow_magnitude = classify_flow_magnitude(flow_pct)

    comments = []

    comments.append(
        f"{fund_code} flow regime: {regime}."
    )

    if cumulative_return > 0 and flow_direction == "Positive":
        comments.append(
            f"The fund generated a positive return and attracted {flow_magnitude.lower()} net inflows."
        )
    elif cumulative_return > 0 and flow_direction == "Neutral":
        comments.append(
            "The fund generated a positive return, while investor flow was economically neutral."
        )
    elif cumulative_return > 0 and flow_direction == "Negative":
        comments.append(
            f"The fund generated a positive return, but experienced {flow_magnitude.lower()} net outflows."
        )
    elif cumulative_return < 0 and flow_direction == "Positive":
        comments.append(
            f"The fund had a negative return, but still attracted {flow_magnitude.lower()} net inflows."
        )
    elif cumulative_return < 0 and flow_direction == "Neutral":
        comments.append(
            "The fund had a negative return, while investor flow was economically neutral."
        )
    elif cumulative_return < 0 and flow_direction == "Negative":
        comments.append(
            f"The fund had a negative return and experienced {flow_magnitude.lower()} net outflows."
        )

    if total_aum_change > 0:
        if abs(total_market_effect) > abs(total_net_flow):
            comments.append(
                f"AUM growth was mainly performance-driven. Market effect was {format_pct(market_pct)}, while net flow was {format_pct(flow_pct)}."
            )
        elif abs(total_net_flow) > abs(total_market_effect):
            comments.append(
                f"AUM growth was mainly flow-driven. Net flow was {format_pct(flow_pct)}, while market effect was {format_pct(market_pct)}."
            )
    elif total_aum_change < 0:
        if total_market_effect < 0 and flow_direction in ["Positive", "Neutral"]:
            comments.append(
                "AUM declined mainly due to negative market performance. Investor flow did not materially worsen the decline."
            )
        elif total_market_effect < 0 and flow_direction == "Negative":
            comments.append(
                "AUM declined due to both negative market performance and investor outflows."
            )

    if participant_change > 0 and flow_direction == "Positive":
        comments.append(
            "Participant growth supports the inflow signal."
        )
    elif participant_change > 0 and flow_direction == "Neutral":
        comments.append(
            "Participant count increased, but the net flow impact was economically small."
        )
    elif participant_change < 0 and flow_direction == "Positive":
        comments.append(
            "Net inflow occurred despite a decline in participant count, suggesting larger average balances or additional contributions by remaining participants."
        )
    elif participant_change < 0 and flow_direction == "Neutral":
        comments.append(
            "Participant count declined, but the net flow impact was economically small."
        )

    if total_net_flow != 0:
        diff_ratio = abs(flow_diff) / abs(total_net_flow)
    else:
        diff_ratio = 0

    if diff_ratio < 0.01:
        comments.append(
            "The unit-based and AUM-based flow estimates are highly consistent."
        )
    elif diff_ratio < 0.05:
        comments.append(
            "The unit-based and AUM-based flow estimates are reasonably consistent."
        )
    else:
        comments.append(
            "The unit-based and AUM-based flow estimates show a noticeable difference and should be reviewed."
        )

    comments.append(
        f"Net flow represented {format_pct(flow_pct)} of starting AUM, while market effect represented {format_pct(market_pct)}."
    )

    return comments


# ============================================================
# 9. Lens Interpretation
# ============================================================

def get_weight_from_table(table: pd.DataFrame, group_name: str) -> float:
    """
    DNA tablosundan belirli bir grubun ağırlığını döndürür.
    Grup yoksa 0 döner.
    """
    if table is None or table.empty:
        return 0

    matched = table.loc[table["group"].eq(group_name), "weight"]

    if matched.empty:
        return 0

    return matched.iloc[0]


def get_top_exposures(dna_table: pd.DataFrame, top_n: int = 3) -> list:
    """
    DNA tablosundan en büyük N exposure'ı döndürür.
    """
    if dna_table is None or dna_table.empty:
        return []

    top_rows = dna_table.sort_values("weight", ascending=False).head(top_n)

    return [
        {
            "group": row["group"],
            "weight": row["weight"],
        }
        for _, row in top_rows.iterrows()
    ]


def classify_fund_archetype(
    broad_table: pd.DataFrame,
    scope_table: pd.DataFrame,
    currency_table: pd.DataFrame,
) -> str:
    """
    Fonun ana karakterini DNA tablosuna göre sınıflandırır.

    Not:
    Bu sınıflandırma bilinçli olarak yorumlayıcıdır.
    AAJ gibi standart/karma fonlarda tekil baskın varlık sınıfı yerine
    'dominant multi-asset' etiketi vermeye çalışır.
    """
    if broad_table is None or broad_table.empty:
        return "Unknown Fund Type"

    fixed_income = get_weight_from_table(broad_table, "Fixed Income")
    equity = get_weight_from_table(broad_table, "Equity")
    foreign_equity = get_weight_from_table(broad_table, "Foreign Equity")
    money_market = get_weight_from_table(broad_table, "Money Market")
    precious_metals = get_weight_from_table(broad_table, "Precious Metals")
    fund_weight = get_weight_from_table(broad_table, "Fund")
    etf_weight = get_weight_from_table(broad_table, "ETF")
    deposit = get_weight_from_table(broad_table, "Deposit")
    participation = get_weight_from_table(broad_table, "Participation Account")
    lease = get_weight_from_table(broad_table, "Lease Certificates")
    real_estate_alt = get_weight_from_table(broad_table, "Real Estate / Alternative")
    venture_alt = get_weight_from_table(broad_table, "Venture Capital / Alternative")

    fx = get_weight_from_table(currency_table, "FX")
    gold = get_weight_from_table(currency_table, "Gold")
    domestic = get_weight_from_table(scope_table, "Domestic")
    foreign = get_weight_from_table(scope_table, "Foreign / International")
    lookthrough = get_weight_from_table(scope_table, "Look-through Required")

    multi_asset_side_weight = (
        equity
        + foreign_equity
        + deposit
        + participation
        + lease
        + fund_weight
        + etf_weight
        + real_estate_alt
        + venture_alt
        + lookthrough
    )

    if precious_metals >= 50 or gold >= 50:
        return "Gold / Precious Metals Fund"

    if fx >= 50 and fixed_income >= 50:
        return "FX / Eurobond Fixed-Income Fund"

    if foreign_equity >= 50:
        return "Foreign Equity Fund"

    if equity >= 50:
        return "Domestic Equity Fund"

    if money_market >= 50:
        return "Money Market Fund"

    if fixed_income >= 50:
        if multi_asset_side_weight >= 20 or equity >= 10 or lookthrough >= 10:
            if domestic >= 50:
                return "Domestic Fixed-Income Dominant Multi-Asset Fund"
            if foreign >= 50:
                return "Foreign Fixed-Income Dominant Multi-Asset Fund"
            return "Fixed-Income Dominant Multi-Asset Fund"

        if domestic >= 50:
            return "Domestic Fixed-Income Fund"
        if foreign >= 50:
            return "Foreign Fixed-Income Fund"

        return "Fixed-Income Fund"

    top_asset = broad_table.iloc[0]["group"]
    top_asset_weight = broad_table.iloc[0]["weight"]

    if top_asset_weight < 50:
        return "Multi-Asset / Mixed Allocation Fund"

    if top_asset == "Fund":
        return "Fund Allocation Dominant Fund"

    return f"{top_asset} Dominant Fund"


def interpret_fund_lens(dna_snapshot: dict, flow_snapshot: dict) -> list:
    """
    DNA ve flow snapshot çıktılarını birlikte yorumlar.
    """
    if dna_snapshot is None or flow_snapshot is None:
        return []

    fund_code = dna_snapshot["fund_code"]

    broad_table = dna_snapshot["broad_table"]
    scope_table = dna_snapshot["scope_table"]
    currency_table = dna_snapshot["currency_table"]

    archetype = classify_fund_archetype(
        broad_table=broad_table,
        scope_table=scope_table,
        currency_table=currency_table,
    )

    top_assets = get_top_exposures(broad_table, top_n=3)
    top_scope = get_top_exposures(scope_table, top_n=2)
    top_currency = get_top_exposures(currency_table, top_n=2)

    cumulative_return = flow_snapshot["cumulative_return"]
    flow_pct = flow_snapshot["flow_pct_start_aum"]
    market_pct = flow_snapshot["market_effect_pct_start_aum"]
    participant_change = flow_snapshot["total_participant_change"]
    regime = flow_snapshot["flow_regime"]

    flow_direction = classify_flow_direction(flow_pct)
    flow_magnitude = classify_flow_magnitude(flow_pct)

    comments = []

    comments.append(
        f"{fund_code} is classified as: {archetype}."
    )

    if top_assets:
        asset_text = ", ".join(
            [f"{item['group']} ({item['weight']:.2f}%)" for item in top_assets]
        )
        comments.append(
            f"The main asset exposures are {asset_text}."
        )

    if top_scope:
        scope_text = ", ".join(
            [f"{item['group']} ({item['weight']:.2f}%)" for item in top_scope]
        )
        comments.append(
            f"Market-scope exposure is mainly {scope_text}."
        )

    if top_currency:
        currency_text = ", ".join(
            [f"{item['group']} ({item['weight']:.2f}%)" for item in top_currency]
        )
        comments.append(
            f"Currency exposure is mainly {currency_text}."
        )

    comments.append(
        f"Recent flow regime is: {regime}."
    )

    if archetype == "Gold / Precious Metals Fund":
        if cumulative_return < 0 and flow_direction in ["Neutral", "Positive"]:
            comments.append(
                "The decline in AUM appears to be mainly driven by gold/precious-metals performance rather than investor withdrawals."
            )
        elif cumulative_return > 0 and flow_direction == "Positive":
            comments.append(
                "The fund benefited from positive precious-metals performance and also received investor inflows."
            )

    elif archetype in ["FX / Eurobond Fixed-Income Fund", "Foreign Fixed-Income Fund"]:
        if cumulative_return > 0 and flow_direction == "Neutral":
            comments.append(
                "Recent AUM growth appears mostly performance-driven, likely linked to FX/eurobond market movements rather than new investor money."
            )
        elif cumulative_return > 0 and flow_direction == "Positive":
            comments.append(
                "The fund benefited from FX/fixed-income performance and also attracted investor inflows."
            )

    elif archetype in [
        "Domestic Fixed-Income Fund",
        "Domestic Fixed-Income Dominant Multi-Asset Fund",
        "Fixed-Income Dominant Multi-Asset Fund",
        "Multi-Asset / Mixed Allocation Fund",
    ]:
        if flow_direction == "Positive" and flow_magnitude in ["Moderate", "Strong"]:
            comments.append(
                "Investor demand appears meaningful relative to the fund size."
            )
        elif flow_direction == "Neutral":
            comments.append(
                "Investor flow is economically neutral; recent AUM movement should be read mostly through market and allocation effects."
            )

    if participant_change > 0 and flow_direction == "Neutral":
        comments.append(
            "Participant count increased, but average net contribution impact was small."
        )

    if participant_change < 0 and flow_direction == "Neutral":
        comments.append(
            "Participant count declined, but the net flow impact was economically small."
        )

    comments.append(
        f"Over the selected period, market effect was {format_pct(market_pct)} and net flow was {format_pct(flow_pct)} of starting AUM."
    )

    return comments


def fund_lens_snapshot(
    fund_code: str,
    lookback_intervals: int = 20,
    lookback: Optional[Union[str, int]] = None,
    language: str = DEFAULT_LANGUAGE,
    verbose: bool = True,
):
    """
    besFundLens birleşik fon raporu:
    DNA + Flow + yorum.
    """
    language = normalize_language(language)
    lookback_intervals = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    fund_code = fund_code.upper()

    dna_snapshot = fund_dna_snapshot(
        fund_code,
        verbose=verbose,
    )

    flow_snapshot = fund_flow_snapshot(
        fund_code,
        lookback_intervals=lookback_intervals,
        verbose=verbose,
    )

    lens_comments = interpret_fund_lens(
        dna_snapshot=dna_snapshot,
        flow_snapshot=flow_snapshot,
    )

    if verbose:
        print("\n" + "=" * 80)
        print(f"besFundLens Interpretation: {fund_code}")
        print("=" * 80)

        for comment in lens_comments:
            print(f"- {comment}")

    return {
        "fund_code": fund_code,
        "language": language,
        "lookback_intervals": lookback_intervals,
        "dna_snapshot": dna_snapshot,
        "flow_snapshot": flow_snapshot,
        "lens_comments": lens_comments,
    }


# ============================================================
# 10. Universe Level Analysis
# ============================================================

def build_lens_record(
    fund_code: str,
    lookback_intervals: int = 20,
    lookback: Optional[Union[str, int]] = None,
    min_start_aum: float = UNIVERSE_MIN_START_AUM,
):
    """
    Tek bir fon için DNA + Flow bilgilerini tek satırlık dict olarak döndürür.

    is_valid_universe_record:
        Universe-level oran analizleri için başlangıç AUM ve katılımcı sayısı
        yeterli olmayan fonları ayırmak amacıyla kullanılır.
    """
    lookback_intervals = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    dna_snapshot = fund_dna_snapshot(
        fund_code,
        verbose=False,
    )

    flow_snapshot = fund_flow_snapshot(
        fund_code,
        lookback_intervals=lookback_intervals,
        verbose=False,
    )

    if dna_snapshot is None or flow_snapshot is None:
        return None

    broad_table = dna_snapshot["broad_table"]
    scope_table = dna_snapshot["scope_table"]
    currency_table = dna_snapshot["currency_table"]

    latest_row = dna_snapshot["latest_row"]

    archetype = classify_fund_archetype(
        broad_table=broad_table,
        scope_table=scope_table,
        currency_table=currency_table,
    )

    top_asset = broad_table.iloc[0] if not broad_table.empty else None
    top_scope = scope_table.iloc[0] if not scope_table.empty else None
    top_currency = currency_table.iloc[0] if not currency_table.empty else None

    start_aum = flow_snapshot["start_aum"]
    end_aum = flow_snapshot["end_aum"]
    start_participants = flow_snapshot["start_participants"]
    end_participants = flow_snapshot["end_participants"]

    is_valid_universe_record = (
        is_finite_number(start_aum)
        and start_aum > min_start_aum
        and is_finite_number(start_participants)
        and start_participants > 0
        and is_finite_number(flow_snapshot["flow_pct_start_aum"])
        and is_finite_number(flow_snapshot["market_effect_pct_start_aum"])
        and is_finite_number(flow_snapshot["total_participant_change_pct"])
    )

    record = {
        "fonKodu": fund_code,
        "fonUnvan": latest_row["fonUnvan"],
        "latest_date": latest_row["tarih"],
        "archetype": archetype,

        "top_asset_group": top_asset["group"] if top_asset is not None else None,
        "top_asset_weight": top_asset["weight"] if top_asset is not None else np.nan,

        "top_scope": top_scope["group"] if top_scope is not None else None,
        "top_scope_weight": top_scope["weight"] if top_scope is not None else np.nan,

        "top_currency": top_currency["group"] if top_currency is not None else None,
        "top_currency_weight": top_currency["weight"] if top_currency is not None else np.nan,

        "lookthrough_weight": get_weight_from_table(
            scope_table,
            "Look-through Required",
        ),

        "start_date": flow_snapshot["start_date"],
        "end_date": flow_snapshot["end_date"],
        "intervals": flow_snapshot["intervals"],
        "start_aum": start_aum,
        "end_aum": end_aum,
        "start_participants": start_participants,
        "end_participants": end_participants,
        "is_valid_universe_record": is_valid_universe_record,

        "cumulative_return": flow_snapshot["cumulative_return"],
        "aum_change_pct": flow_snapshot["total_aum_change_pct"],
        "market_effect_pct": flow_snapshot["market_effect_pct_start_aum"],
        "flow_pct": flow_snapshot["flow_pct_start_aum"],
        "participant_change_pct": flow_snapshot["total_participant_change_pct"],
        "flow_regime": flow_snapshot["flow_regime"],

        "total_net_flow": flow_snapshot["total_net_flow_unit"],
        "total_market_effect": flow_snapshot["total_market_effect"],
        "participant_change": flow_snapshot["total_participant_change"],
    }

    return record


def build_lens_universe(
    lookback_intervals: int = 20,
    lookback: Optional[Union[str, int]] = None,
    fund_codes: Optional[Sequence[str]] = None,
    valid_only: bool = True,
    min_start_aum: float = UNIVERSE_MIN_START_AUM,
) -> pd.DataFrame:
    """
    Tüm fon evreni için lens tablosu üretir.

    valid_only=True:
        Başlangıç AUM'u çok düşük/sıfır olan veya oran metrikleri geçersiz olan
        fonları universe-level sıralamalardan çıkarır.
    """
    lookback_intervals = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    fund_codes = normalize_fund_codes(fund_codes)

    if fund_codes is None:
        fund_codes = sorted(df_panel_dna["fonKodu"].dropna().unique())

    lens_records = []

    for code in fund_codes:
        record = build_lens_record(
            code,
            lookback_intervals=lookback_intervals,
            min_start_aum=min_start_aum,
        )

        if record is not None:
            lens_records.append(record)

    lens_universe_df = pd.DataFrame(lens_records)

    if lens_universe_df.empty:
        return lens_universe_df

    # Sonsuz değer kalmışsa analiz listelerini bozmaması için NaN'a çeviriyoruz.
    lens_universe_df = lens_universe_df.replace([np.inf, -np.inf], np.nan)

    if valid_only and "is_valid_universe_record" in lens_universe_df.columns:
        lens_universe_df = lens_universe_df[
            lens_universe_df["is_valid_universe_record"].eq(True)
        ].copy()

    return lens_universe_df.reset_index(drop=True)


def get_top_inflows(lens_universe_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    return (
        lens_universe_df
        .sort_values("flow_pct", ascending=False)
        [
            [
                "fonKodu",
                "archetype",
                "flow_regime",
                "flow_pct",
                "participant_change_pct",
                "market_effect_pct",
                "top_asset_group",
                "top_currency",
            ]
        ]
        .head(n)
    )


def get_top_outflows(lens_universe_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    return (
        lens_universe_df
        .sort_values("flow_pct", ascending=True)
        [
            [
                "fonKodu",
                "archetype",
                "flow_regime",
                "flow_pct",
                "participant_change_pct",
                "market_effect_pct",
                "top_asset_group",
                "top_currency",
            ]
        ]
        .head(n)
    )


def get_pure_performance_driven(lens_universe_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    pure_performance_driven = lens_universe_df[
        (lens_universe_df["market_effect_pct"] > 0.01)
        & (lens_universe_df["flow_pct"].abs() < 0.0005)
    ].copy()

    return (
        pure_performance_driven
        .sort_values("market_effect_pct", ascending=False)
        [
            [
                "fonKodu",
                "archetype",
                "market_effect_pct",
                "flow_pct",
                "flow_regime",
                "top_asset_group",
                "top_currency",
            ]
        ]
        .head(n)
    )


def get_performance_led(lens_universe_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    performance_led = lens_universe_df[
        (lens_universe_df["market_effect_pct"] > 0.01)
        & (lens_universe_df["market_effect_pct"].abs() > lens_universe_df["flow_pct"].abs())
    ].copy()

    return (
        performance_led
        .sort_values("market_effect_pct", ascending=False)
        [
            [
                "fonKodu",
                "archetype",
                "market_effect_pct",
                "flow_pct",
                "flow_regime",
                "top_asset_group",
                "top_currency",
            ]
        ]
        .head(n)
    )


def get_participant_growth_neutral_flow(
    lens_universe_df: pd.DataFrame,
    n: int = 20,
) -> pd.DataFrame:
    participant_growth_neutral_flow = lens_universe_df[
        (lens_universe_df["participant_change_pct"] > 0.005)
        & (lens_universe_df["flow_pct"].abs() < 0.0005)
    ].copy()

    return (
        participant_growth_neutral_flow
        .sort_values("participant_change_pct", ascending=False)
        [
            [
                "fonKodu",
                "archetype",
                "participant_change_pct",
                "flow_pct",
                "market_effect_pct",
                "flow_regime",
            ]
        ]
        .head(n)
    )


def get_high_lookthrough(lens_universe_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    return (
        lens_universe_df
        .sort_values("lookthrough_weight", ascending=False)
        [
            [
                "fonKodu",
                "archetype",
                "lookthrough_weight",
                "top_asset_group",
                "top_currency",
                "flow_regime",
            ]
        ]
        .head(n)
    )


def validate_lens_universe(lens_universe_df: pd.DataFrame):
    """
    Universe çıktısında sonsuz / aşırı değerleri ve kalite kolonlarını hızlı kontrol eder.
    """
    required_cols = [
        "flow_pct",
        "participant_change_pct",
        "market_effect_pct",
        "start_aum",
        "start_participants",
        "is_valid_universe_record",
    ]

    missing_cols = [col for col in required_cols if col not in lens_universe_df.columns]
    print("Missing universe validation columns:", missing_cols)

    numeric_cols = [
        col for col in ["flow_pct", "participant_change_pct", "market_effect_pct"]
        if col in lens_universe_df.columns
    ]

    if numeric_cols:
        finite_mask = np.isfinite(lens_universe_df[numeric_cols]).all(axis=1)
        print("Rows:", len(lens_universe_df))
        print("Finite rows:", int(finite_mask.sum()))
        print("Non-finite rows:", int((~finite_mask).sum()))
        print(lens_universe_df[numeric_cols].describe())

    if "is_valid_universe_record" in lens_universe_df.columns:
        print("Valid universe records:")
        print(lens_universe_df["is_valid_universe_record"].value_counts(dropna=False))




# ============================================================
# 11. Universe Segmentation, Quadrants and Reporting
# ============================================================

def classify_direction(value, neutral_threshold: float = 0.0005) -> str:
    """
    Genel pozitif / negatif / nötr yön sınıflandırması.
    """
    if not is_finite_number(value):
        return "Unknown"

    if value > neutral_threshold:
        return "Positive"
    if value < -neutral_threshold:
        return "Negative"
    return "Neutral"


def classify_aum_segment(start_aum) -> str:
    """
    Fonun başlangıç AUM seviyesine göre büyüklük segmenti.
    """
    if not is_finite_number(start_aum):
        return "Unknown"

    if start_aum < 100_000_000:
        return "Small AUM"
    if start_aum < 1_000_000_000:
        return "Mid AUM"
    if start_aum < 10_000_000_000:
        return "Large AUM"
    return "Mega AUM"


def classify_participant_segment(start_participants) -> str:
    """
    Fonun başlangıç katılımcı sayısına göre katılımcı tabanı segmenti.
    """
    if not is_finite_number(start_participants):
        return "Unknown"

    if start_participants < 1_000:
        return "Small Participant Base"
    if start_participants < 10_000:
        return "Mid Participant Base"
    if start_participants < 100_000:
        return "Large Participant Base"
    return "Mega Participant Base"


def classify_flow_intensity(flow_pct) -> str:
    """
    Net flow büyüklüğünü daha açıklayıcı segmentlere ayırır.
    """
    if not is_finite_number(flow_pct):
        return "Unknown"

    abs_flow = abs(flow_pct)

    if abs_flow < 0.0005:
        return "Neutral"
    if abs_flow < 0.0025:
        return "Small"
    if abs_flow < 0.01:
        return "Moderate"
    if abs_flow < 0.05:
        return "Strong"
    if abs_flow < 0.25:
        return "Very Strong"
    return "Extreme"


def add_universe_segments(lens_universe_df: pd.DataFrame) -> pd.DataFrame:
    """
    Universe tablosuna AUM, katılımcı ve flow intensity segmentleri ekler.
    """
    df = lens_universe_df.copy()

    df["aum_segment"] = df["start_aum"].apply(classify_aum_segment)
    df["participant_segment"] = df["start_participants"].apply(
        classify_participant_segment
    )
    df["flow_intensity"] = df["flow_pct"].apply(classify_flow_intensity)

    return df


def get_established_funds(
    lens_universe_df: pd.DataFrame,
    min_start_aum: float = 1_000_000_000,
    min_start_participants: int = 10_000,
) -> pd.DataFrame:
    """
    Daha karşılaştırılabilir, oturmuş fon evrenini döndürür.
    """
    return lens_universe_df[
        (lens_universe_df["start_aum"] >= min_start_aum)
        & (lens_universe_df["start_participants"] >= min_start_participants)
    ].copy()


def get_high_growth_funds(
    lens_universe_df: pd.DataFrame,
    min_flow_pct: float = 0.25,
    n: int = 30,
) -> pd.DataFrame:
    """
    Başlangıç AUM'una göre çok güçlü net giriş alan fonları listeler.
    """
    high_growth_funds_df = lens_universe_df[
        lens_universe_df["flow_pct"] > min_flow_pct
    ].copy()

    columns = [
        "fonKodu",
        "archetype",
        "start_aum",
        "aum_segment",
        "start_participants",
        "participant_segment",
        "flow_pct",
        "participant_change_pct",
        "market_effect_pct",
        "flow_regime",
    ]

    available_columns = [col for col in columns if col in high_growth_funds_df.columns]

    return (
        high_growth_funds_df
        .sort_values("flow_pct", ascending=False)
        [available_columns]
        .head(n)
    )


def summarize_lens_universe(lens_universe_df: pd.DataFrame) -> pd.Series:
    """
    Universe seviyesinde kısa özet üretir.
    """
    df = lens_universe_df.copy()

    summary = {
        "fund_count": df.shape[0],
        "total_start_aum": df["start_aum"].sum(),
        "total_end_aum": df["end_aum"].sum(),
        "total_net_flow": df["total_net_flow"].sum(),
        "total_market_effect": df["total_market_effect"].sum(),
        "avg_flow_pct": df["flow_pct"].mean(),
        "median_flow_pct": df["flow_pct"].median(),
        "avg_market_effect_pct": df["market_effect_pct"].mean(),
        "median_market_effect_pct": df["market_effect_pct"].median(),
    }

    return pd.Series(summary)


def summarize_lens_by(
    lens_universe_df: pd.DataFrame,
    group_col: str,
    min_funds: int = 1,
) -> pd.DataFrame:
    """
    Universe tablosunu seçilen kırılıma göre özetler.

    group_col örnekleri:
        - archetype
        - aum_segment
        - participant_segment
        - top_asset_group
        - top_currency
        - flow_intensity
        - market_flow_quadrant
    """
    df = lens_universe_df.copy()

    if group_col not in df.columns:
        raise ValueError(f"{group_col} kolonu lens_universe_df içinde yok.")

    universe_start_aum = df["start_aum"].sum()
    rows = []

    for group_name, group_df in df.groupby(group_col, dropna=False):
        total_start_aum = group_df["start_aum"].sum()
        total_end_aum = group_df["end_aum"].sum()
        total_net_flow = group_df["total_net_flow"].sum()
        total_market_effect = group_df["total_market_effect"].sum()
        total_participant_change = group_df["participant_change"].sum()

        weighted_flow_pct = safe_divide(total_net_flow, total_start_aum)
        weighted_market_effect_pct = safe_divide(total_market_effect, total_start_aum)
        weighted_aum_change_pct = safe_divide(total_end_aum, total_start_aum) - 1
        start_aum_share = safe_divide(total_start_aum, universe_start_aum)

        rows.append({
            group_col: group_name,
            "fund_count": group_df.shape[0],
            "start_aum_share": start_aum_share,
            "total_start_aum": total_start_aum,
            "total_end_aum": total_end_aum,
            "weighted_aum_change_pct": weighted_aum_change_pct,
            "weighted_flow_pct": weighted_flow_pct,
            "weighted_market_effect_pct": weighted_market_effect_pct,
            "total_net_flow": total_net_flow,
            "total_market_effect": total_market_effect,
            "total_participant_change": total_participant_change,
            "avg_flow_pct": group_df["flow_pct"].mean(),
            "median_flow_pct": group_df["flow_pct"].median(),
            "avg_participant_change_pct": group_df["participant_change_pct"].mean(),
            "median_participant_change_pct": group_df["participant_change_pct"].median(),
        })

    summary_df = pd.DataFrame(rows)

    if summary_df.empty:
        return summary_df

    summary_df = summary_df[summary_df["fund_count"] >= min_funds].copy()

    return (
        summary_df
        .sort_values("total_start_aum", ascending=False)
        .reset_index(drop=True)
    )


def interpret_segment_summary(
    summary_df: pd.DataFrame,
    group_col: str,
    top_n: int = 5,
) -> list:
    """
    Segment özet tablosundan kısa yorumlar üretir.
    """
    comments = []

    if summary_df.empty:
        return ["No segment data available."]

    largest_segments = summary_df.sort_values(
        "total_start_aum",
        ascending=False,
    ).head(top_n)

    strongest_inflows = summary_df.sort_values(
        "weighted_flow_pct",
        ascending=False,
    ).head(top_n)

    strongest_outflows = summary_df.sort_values(
        "weighted_flow_pct",
        ascending=True,
    ).head(top_n)

    weakest_market_effect = summary_df.sort_values(
        "weighted_market_effect_pct",
        ascending=True,
    ).head(top_n)

    strongest_market_effect = summary_df.sort_values(
        "weighted_market_effect_pct",
        ascending=False,
    ).head(top_n)

    comments.append("Largest segments by starting AUM:")
    for _, row in largest_segments.iterrows():
        comments.append(
            f"- {row[group_col]}: {format_pct(row['start_aum_share'])} of universe AUM."
        )

    comments.append("Strongest weighted net inflow segments:")
    for _, row in strongest_inflows.iterrows():
        comments.append(
            f"- {row[group_col]}: weighted flow {format_pct(row['weighted_flow_pct'])}."
        )

    comments.append("Strongest weighted net outflow segments:")
    for _, row in strongest_outflows.iterrows():
        comments.append(
            f"- {row[group_col]}: weighted flow {format_pct(row['weighted_flow_pct'])}."
        )

    comments.append("Most negative market-effect segments:")
    for _, row in weakest_market_effect.iterrows():
        comments.append(
            f"- {row[group_col]}: market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    comments.append("Most positive market-effect segments:")
    for _, row in strongest_market_effect.iterrows():
        comments.append(
            f"- {row[group_col]}: market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    return comments


def classify_market_flow_quadrant(
    market_effect_pct,
    flow_pct,
    threshold: float = 0.0005,
) -> str:
    """
    Market effect ve net flow ilişkisine göre fonu/segmenti quadrant'a ayırır.

    threshold:
        ±0.05% altındaki hareketler ekonomik olarak nötr kabul edilir.
    """
    market_direction = classify_direction(
        market_effect_pct,
        neutral_threshold=threshold,
    )

    flow_direction = classify_flow_direction(
        flow_pct,
        threshold=threshold,
    )

    if market_direction == "Positive" and flow_direction == "Positive":
        return "Positive Market / Positive Flow"
    if market_direction == "Positive" and flow_direction == "Negative":
        return "Positive Market / Negative Flow"
    if market_direction == "Negative" and flow_direction == "Positive":
        return "Negative Market / Positive Flow"
    if market_direction == "Negative" and flow_direction == "Negative":
        return "Negative Market / Negative Flow"
    if market_direction == "Positive" and flow_direction == "Neutral":
        return "Positive Market / Neutral Flow"
    if market_direction == "Negative" and flow_direction == "Neutral":
        return "Negative Market / Neutral Flow"
    if market_direction == "Neutral" and flow_direction == "Positive":
        return "Neutral Market / Positive Flow"
    if market_direction == "Neutral" and flow_direction == "Negative":
        return "Neutral Market / Negative Flow"
    if market_direction == "Unknown" or flow_direction == "Unknown":
        return "Unknown Market / Unknown Flow"

    return "Neutral Market / Neutral Flow"


def add_market_flow_quadrant(lens_universe_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fon bazlı universe tablosuna market-flow quadrant kolonu ekler.
    """
    df = lens_universe_df.copy()

    df["market_flow_quadrant"] = df.apply(
        lambda row: classify_market_flow_quadrant(
            row["market_effect_pct"],
            row["flow_pct"],
        ),
        axis=1,
    )

    return df


def interpret_quadrant_summary(quadrant_summary: pd.DataFrame) -> list:
    """
    Market-flow quadrant özetinden kısa yorum üretir.
    """
    comments = []

    if quadrant_summary.empty:
        return ["No quadrant summary available."]

    largest = quadrant_summary.sort_values(
        "start_aum_share",
        ascending=False,
    ).head(3)

    comments.append("Largest market-flow regimes by starting AUM:")

    for _, row in largest.iterrows():
        comments.append(
            f"- {row['market_flow_quadrant']}: "
            f"{format_pct(row['start_aum_share'])} of universe AUM, "
            f"flow {format_pct(row['weighted_flow_pct'])}, "
            f"market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    negative_market = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Negative Market",
            na=False,
        )
    ]

    if not negative_market.empty:
        negative_market_aum_share = negative_market["start_aum_share"].sum()
        comments.append(
            f"Negative-market regimes represent {format_pct(negative_market_aum_share)} of universe AUM."
        )

    positive_flow = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Positive Flow",
            na=False,
        )
    ]

    if not positive_flow.empty:
        positive_flow_aum_share = positive_flow["start_aum_share"].sum()
        comments.append(
            f"Positive-flow regimes represent {format_pct(positive_flow_aum_share)} of universe AUM."
        )

    return comments


def build_archetype_quadrant_aum_tables(lens_universe_df: pd.DataFrame):
    """
    Archetype x Market-Flow Quadrant için AUM tutarı ve satır içi AUM payı tablolarını üretir.
    """
    if "market_flow_quadrant" not in lens_universe_df.columns:
        lens_universe_df = add_market_flow_quadrant(lens_universe_df)

    amount_table = pd.pivot_table(
        lens_universe_df,
        index="archetype",
        columns="market_flow_quadrant",
        values="start_aum",
        aggfunc="sum",
        fill_value=0,
    )

    share_table = amount_table.div(
        amount_table.sum(axis=1).replace(0, np.nan),
        axis=0,
    ).fillna(0)

    return amount_table, share_table


def generate_market_narrative_report(
    lens_universe_df: pd.DataFrame,
    top_n: int = 5,
    verbose: bool = True,
) -> dict:
    """
    besFundLens universe seviyesinde kısa piyasa anlatısı üretir.
    """
    df = lens_universe_df.copy()

    if "market_flow_quadrant" not in df.columns:
        df = add_market_flow_quadrant(df)

    universe_summary = summarize_lens_universe(df)

    archetype_summary = summarize_lens_by(
        df,
        group_col="archetype",
        min_funds=3,
    )

    quadrant_summary = summarize_lens_by(
        df,
        group_col="market_flow_quadrant",
    )

    report = {
        "universe_summary": universe_summary,
        "archetype_summary": archetype_summary,
        "quadrant_summary": quadrant_summary,
    }

    if not verbose:
        return report

    print("=" * 80)
    print("besFundLens Market Narrative Report")
    print("=" * 80)

    print("\nUniverse Overview")
    print("-" * 80)
    print(f"Fund count          : {int(universe_summary['fund_count']):,}")
    print(f"Total start AUM     : {format_try(universe_summary['total_start_aum'])}")
    print(f"Total end AUM       : {format_try(universe_summary['total_end_aum'])}")
    print(f"Total net flow      : {format_try(universe_summary['total_net_flow'])}")
    print(f"Total market effect : {format_try(universe_summary['total_market_effect'])}")

    total_aum_change_pct = (
        safe_divide(
            universe_summary["total_end_aum"],
            universe_summary["total_start_aum"],
        ) - 1
    )

    total_flow_pct = safe_divide(
        universe_summary["total_net_flow"],
        universe_summary["total_start_aum"],
    )

    total_market_pct = safe_divide(
        universe_summary["total_market_effect"],
        universe_summary["total_start_aum"],
    )

    print(f"Total AUM change %  : {format_pct(total_aum_change_pct)}")
    print(f"Total net flow %    : {format_pct(total_flow_pct)}")
    print(f"Market effect %     : {format_pct(total_market_pct)}")

    print("\nMain Narrative")
    print("-" * 80)

    if universe_summary["total_net_flow"] > 0 and universe_summary["total_market_effect"] < 0:
        print(
            "- The universe received positive net inflows, but negative market performance dominated the total AUM movement."
        )
    elif universe_summary["total_net_flow"] < 0 and universe_summary["total_market_effect"] < 0:
        print(
            "- The universe faced both net outflows and negative market performance."
        )
    elif universe_summary["total_net_flow"] > 0 and universe_summary["total_market_effect"] > 0:
        print(
            "- The universe benefited from both positive investor flows and positive market performance."
        )
    else:
        print(
            "- The universe showed a mixed market-flow profile."
        )

    negative_market_share = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Negative Market",
            na=False,
        )
    ]["start_aum_share"].sum()

    positive_flow_share = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Positive Flow",
            na=False,
        )
    ]["start_aum_share"].sum()

    print(
        f"- Negative-market regimes represent {format_pct(negative_market_share)} of universe AUM."
    )
    print(
        f"- Positive-flow regimes represent {format_pct(positive_flow_share)} of universe AUM."
    )

    print("\nLargest Archetypes by Starting AUM")
    print("-" * 80)

    for _, row in archetype_summary.head(top_n).iterrows():
        print(
            f"- {row['archetype']}: "
            f"{format_pct(row['start_aum_share'])} of AUM, "
            f"flow {format_pct(row['weighted_flow_pct'])}, "
            f"market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    print("\nMarket-Flow Quadrants")
    print("-" * 80)

    for _, row in quadrant_summary.head(top_n).iterrows():
        print(
            f"- {row['market_flow_quadrant']}: "
            f"{format_pct(row['start_aum_share'])} of AUM, "
            f"flow {format_pct(row['weighted_flow_pct'])}, "
            f"market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    print("\nStrongest Inflow Archetypes")
    print("-" * 80)

    strongest_inflows = archetype_summary.sort_values(
        "weighted_flow_pct",
        ascending=False,
    ).head(top_n)

    for _, row in strongest_inflows.iterrows():
        print(
            f"- {row['archetype']}: weighted flow {format_pct(row['weighted_flow_pct'])}."
        )

    print("\nMost Negative Market-Effect Archetypes")
    print("-" * 80)

    weakest_market = archetype_summary.sort_values(
        "weighted_market_effect_pct",
        ascending=True,
    ).head(top_n)

    for _, row in weakest_market.iterrows():
        print(
            f"- {row['archetype']}: market effect {format_pct(row['weighted_market_effect_pct'])}."
        )

    return report


def classify_dominance_strength(dominant_share) -> str:
    """
    Dominant quadrant'ın gerçekten baskın olup olmadığını sınıflandırır.
    """
    if not is_finite_number(dominant_share):
        return "Unknown"

    if dominant_share >= 0.75:
        return "High dominance"
    if dominant_share >= 0.50:
        return "Moderate dominance"
    if dominant_share >= 0.35:
        return "Weak dominance"
    return "Fragmented"


def summarize_dominant_quadrant_by_archetype(lens_universe_df: pd.DataFrame) -> pd.DataFrame:
    """
    Her archetype için AUM ağırlıklı dominant market-flow quadrant'ı bulur.
    Ayrıca dominant rejimin ne kadar güçlü olduğunu sınıflandırır.
    """
    amount_table, share_table = build_archetype_quadrant_aum_tables(
        lens_universe_df
    )

    rows = []

    for archetype in share_table.index:
        row = share_table.loc[archetype]

        dominant_quadrant = row.idxmax()
        dominant_share = row.max()
        total_start_aum = amount_table.loc[archetype].sum()

        rows.append({
            "archetype": archetype,
            "dominant_quadrant": dominant_quadrant,
            "dominant_quadrant_share": dominant_share,
            "dominance_strength": classify_dominance_strength(dominant_share),
            "total_start_aum": total_start_aum,
        })

    result = pd.DataFrame(rows)

    return (
        result
        .sort_values("total_start_aum", ascending=False)
        .reset_index(drop=True)
    )


def interpret_dominant_quadrants(
    dominant_quadrant_df: pd.DataFrame,
    top_n: int = 10,
) -> list:
    """
    Dominant quadrant tablosundan daha nüanslı yorum üretir.
    """
    comments = []

    for _, row in dominant_quadrant_df.head(top_n).iterrows():
        archetype = row["archetype"]
        quadrant = row["dominant_quadrant"]
        share = row["dominant_quadrant_share"]
        strength = row["dominance_strength"]

        if strength == "High dominance":
            comments.append(
                f"{archetype}: clear regime concentration — "
                f"{format_pct(share)} of AUM is in {quadrant}."
            )
        elif strength == "Moderate dominance":
            comments.append(
                f"{archetype}: moderately concentrated regime — "
                f"{format_pct(share)} of AUM is in {quadrant}."
            )
        elif strength == "Weak dominance":
            comments.append(
                f"{archetype}: fragmented behavior with a weak leading regime — "
                f"{format_pct(share)} of AUM is in {quadrant}."
            )
        else:
            comments.append(
                f"{archetype}: highly fragmented behavior across market-flow regimes."
            )

    return comments


def generate_archetype_insights(
    dominant_quadrant_df: pd.DataFrame,
    top_n: int = 10,
    language: str = DEFAULT_LANGUAGE,
) -> pd.DataFrame:
    """
    Generate concise archetype-level insights from dominant market-flow regimes.

    The output is localized with the `language` parameter.
    Archetype names are intentionally kept in English for global readability.
    """
    language = normalize_language(language)
    insights = []

    for _, row in dominant_quadrant_df.head(top_n).iterrows():
        archetype = row["archetype"]
        quadrant = row["dominant_quadrant"]
        share = row["dominant_quadrant_share"]
        strength = row["dominance_strength"]
        pattern_message = get_quadrant_pattern_message(quadrant, language=language)

        if language == "tr":
            if strength == "High dominance":
                insight = (
                    f"{archetype} için belirgin rejim yoğunlaşması var: "
                    f"{pattern_message}."
                )
            elif strength == "Moderate dominance":
                insight = (
                    f"{archetype} için orta düzeyde rejim yoğunlaşması var: "
                    f"{pattern_message}. İç dağılımda belirli ölçüde farklılaşma mevcut."
                )
            elif strength == "Weak dominance":
                insight = (
                    f"{archetype} içinde davranış parçalı; yalnızca zayıf bir eğilim olarak "
                    f"şu desen öne çıkıyor: {pattern_message}."
                )
            else:
                insight = (
                    f"{archetype} farklı piyasa-akış rejimlerine dağılmış durumda; "
                    "tek bir rejim aşırı yorumlanmamalıdır."
                )
        else:
            if strength == "High dominance":
                insight = (
                    f"{archetype} has a clear regime concentration: "
                    f"{pattern_message}."
                )
            elif strength == "Moderate dominance":
                insight = (
                    f"{archetype} has a moderately concentrated regime: "
                    f"{pattern_message}. Some internal dispersion exists."
                )
            elif strength == "Weak dominance":
                insight = (
                    f"{archetype} is internally mixed, with only a weak tilt toward this pattern: "
                    f"{pattern_message}."
                )
            else:
                insight = (
                    f"{archetype} has fragmented behavior across market-flow regimes; "
                    "no single regime should be over-interpreted."
                )

        insights.append({
            "archetype": archetype,
            "dominant_quadrant": quadrant,
            "dominant_quadrant_label": translate_quadrant_name(
                quadrant,
                language=language,
            ),
            "dominant_quadrant_share": share,
            "dominance_strength": strength,
            "dominance_strength_label": translate_dominance_strength(
                strength,
                language=language,
            ),
            "insight": insight,
        })

    return pd.DataFrame(insights)


# ============================================================
# 11.1. Bilingual Report Labels
# ============================================================

REPORT_LABELS = {
    "en": {
        "market_report_title": "# besFundLens Market Narrative Report",
        "selected_report_title": "# Selected Funds Comparison Report",
        "executive_summary": "## Executive Summary",
        "main_narrative": "## Main Narrative",
        "largest_archetypes": "## Largest Archetypes by Starting AUM",
        "market_flow_quadrants": "## Market-Flow Quadrants",
        "strongest_inflow_archetypes": "## Strongest Inflow Archetypes",
        "most_negative_market_effect": "## Most Negative Market-Effect Archetypes",
        "dominant_regime_by_archetype": "## Dominant Market-Flow Regime by Archetype",
        "interpretation_notes": "## Interpretation Notes",
        "fund_comparison": "## Fund Comparison",
        "fund_universe_count": "Fund universe count",
        "total_start_aum": "Total start AUM",
        "total_end_aum": "Total end AUM",
        "total_aum_change": "Total AUM change",
        "total_net_flow": "Total net flow",
        "total_market_effect": "Total market effect",
        "of_starting_aum": "of starting AUM",
        "archetype": "Archetype",
        "aum_share": "AUM Share",
        "flow": "Flow",
        "weighted_flow": "Weighted Flow",
        "market_effect": "Market Effect",
        "aum_change": "AUM Change",
        "fund_count": "Fund Count",
        "quadrant": "Quadrant",
        "dominant_regime": "Dominant Regime",
        "aum_share_in_regime": "AUM Share in Regime",
        "strength": "Strength",
        "insight": "Insight",
        "fund": "Fund",
        "return": "Return",
        "participant_change": "Participant Change",
        "regime": "Regime",
        "no_selected_data": "No selected fund data available.",
        "note_flow": "`Flow` represents estimated investor net flow as a percentage of starting AUM.",
        "note_market_effect": "`Market Effect` represents the estimated AUM impact of fund return.",
        "note_aum_change": "`AUM Change` is approximately the sum of Flow and Market Effect.",
        "note_dominant_regime": "`Dominant Regime` shows the largest AUM-weighted market-flow quadrant within each archetype.",
        "note_strength": "`Strength` indicates whether the dominant regime is clearly concentrated or fragmented.",
        "note_lookthrough": "Look-through-heavy funds should be analyzed with additional underlying fund exposure data.",
    },
    "tr": {
        "market_report_title": "# besFundLens Piyasa Anlatı Raporu",
        "selected_report_title": "# Seçili Fon Karşılaştırma Raporu",
        "executive_summary": "## Yönetici Özeti",
        "main_narrative": "## Ana Anlatı",
        "largest_archetypes": "## Başlangıç AUM'a Göre En Büyük Fon Tipleri",
        "market_flow_quadrants": "## Piyasa-Akış Rejimleri",
        "strongest_inflow_archetypes": "## En Güçlü Net Giriş Alan Fon Tipleri",
        "most_negative_market_effect": "## En Negatif Piyasa Etkisine Sahip Fon Tipleri",
        "dominant_regime_by_archetype": "## Fon Tipine Göre Baskın Piyasa-Akış Rejimi",
        "interpretation_notes": "## Yorum Notları",
        "fund_comparison": "## Fon Karşılaştırması",
        "fund_universe_count": "Fon evrenindeki fon sayısı",
        "total_start_aum": "Toplam başlangıç AUM",
        "total_end_aum": "Toplam bitiş AUM",
        "total_aum_change": "Toplam AUM değişimi",
        "total_net_flow": "Toplam net akış",
        "total_market_effect": "Toplam piyasa etkisi",
        "of_starting_aum": "başlangıç AUM'a göre",
        "archetype": "Fon Tipi",
        "aum_share": "AUM Payı",
        "flow": "Akış",
        "weighted_flow": "Ağırlıklı Akış",
        "market_effect": "Piyasa Etkisi",
        "aum_change": "AUM Değişimi",
        "fund_count": "Fon Sayısı",
        "quadrant": "Rejim",
        "dominant_regime": "Baskın Rejim",
        "aum_share_in_regime": "Rejim İçindeki AUM Payı",
        "strength": "Yoğunlaşma",
        "insight": "Yorum",
        "fund": "Fon",
        "return": "Getiri",
        "participant_change": "Katılımcı Değişimi",
        "regime": "Rejim",
        "no_selected_data": "Seçili fon verisi bulunamadı.",
        "note_flow": "`Akış`, başlangıç AUM'a göre tahmini yatırımcı net akışını gösterir.",
        "note_market_effect": "`Piyasa Etkisi`, fon getirisinin tahmini AUM etkisini gösterir.",
        "note_aum_change": "`AUM Değişimi`, yaklaşık olarak Akış ve Piyasa Etkisi toplamıdır.",
        "note_dominant_regime": "`Baskın Rejim`, her fon tipi içinde AUM ağırlıklı en büyük piyasa-akış rejimini gösterir.",
        "note_strength": "`Yoğunlaşma`, baskın rejimin net şekilde yoğunlaşıp yoğunlaşmadığını veya parçalı olup olmadığını gösterir.",
        "note_lookthrough": "Look-through ağırlığı yüksek fonlar, alt fon kırılımlarıyla ayrıca analiz edilmelidir.",
    },
}

QUADRANT_TRANSLATIONS = {
    "en": {
        "Negative Market / Negative Flow": "Negative Market / Negative Flow",
        "Negative Market / Positive Flow": "Negative Market / Positive Flow",
        "Positive Market / Negative Flow": "Positive Market / Negative Flow",
        "Positive Market / Positive Flow": "Positive Market / Positive Flow",
        "Negative Market / Neutral Flow": "Negative Market / Neutral Flow",
        "Positive Market / Neutral Flow": "Positive Market / Neutral Flow",
        "Neutral Market / Positive Flow": "Neutral Market / Positive Flow",
        "Neutral Market / Negative Flow": "Neutral Market / Negative Flow",
        "Neutral Market / Neutral Flow": "Neutral Market / Neutral Flow",
    },
    "tr": {
        "Negative Market / Negative Flow": "Negatif Piyasa / Negatif Akış",
        "Negative Market / Positive Flow": "Negatif Piyasa / Pozitif Akış",
        "Positive Market / Negative Flow": "Pozitif Piyasa / Negatif Akış",
        "Positive Market / Positive Flow": "Pozitif Piyasa / Pozitif Akış",
        "Negative Market / Neutral Flow": "Negatif Piyasa / Nötr Akış",
        "Positive Market / Neutral Flow": "Pozitif Piyasa / Nötr Akış",
        "Neutral Market / Positive Flow": "Nötr Piyasa / Pozitif Akış",
        "Neutral Market / Negative Flow": "Nötr Piyasa / Negatif Akış",
        "Neutral Market / Neutral Flow": "Nötr Piyasa / Nötr Akış",
    },
}

DOMINANCE_TRANSLATIONS = {
    "en": {
        "High dominance": "High dominance",
        "Moderate dominance": "Moderate dominance",
        "Weak dominance": "Weak dominance",
        "Fragmented": "Fragmented",
        "Unknown": "Unknown",
    },
    "tr": {
        "High dominance": "Yüksek yoğunlaşma",
        "Moderate dominance": "Orta düzey yoğunlaşma",
        "Weak dominance": "Zayıf yoğunlaşma",
        "Fragmented": "Parçalı",
        "Unknown": "Bilinmiyor",
    },
}

QUADRANT_PATTERN_MESSAGES = {
    "en": {
        "Negative Market / Negative Flow": "market performance and investor flows are both under pressure",
        "Negative Market / Positive Flow": "investor flows are positive despite negative market performance",
        "Positive Market / Negative Flow": "market performance is positive, but investor flows are negative, possibly indicating profit-taking or rotation",
        "Positive Market / Positive Flow": "both market performance and investor flows are positive",
        "Negative Market / Neutral Flow": "market performance is negative while investor flow is broadly neutral",
        "Positive Market / Neutral Flow": "market performance is positive while investor flow is broadly neutral",
        "Neutral Market / Positive Flow": "investor flows are positive while market impact is broadly neutral",
        "Neutral Market / Negative Flow": "investor flows are negative while market impact is broadly neutral",
        "Neutral Market / Neutral Flow": "both market impact and investor flow are broadly neutral",
    },
    "tr": {
        "Negative Market / Negative Flow": "piyasa performansı ve yatırımcı akışları aynı anda baskı altında",
        "Negative Market / Positive Flow": "negatif piyasa performansına rağmen yatırımcı akışları pozitif",
        "Positive Market / Negative Flow": "piyasa performansı pozitif ancak yatırımcı akışları negatif; bu durum kâr realizasyonu veya rotasyon sinyali olabilir",
        "Positive Market / Positive Flow": "piyasa performansı ve yatırımcı akışları aynı anda pozitif",
        "Negative Market / Neutral Flow": "piyasa performansı negatifken yatırımcı akışı genel olarak nötr",
        "Positive Market / Neutral Flow": "piyasa performansı pozitifken yatırımcı akışı genel olarak nötr",
        "Neutral Market / Positive Flow": "piyasa etkisi genel olarak nötrken yatırımcı akışları pozitif",
        "Neutral Market / Negative Flow": "piyasa etkisi genel olarak nötrken yatırımcı akışları negatif",
        "Neutral Market / Neutral Flow": "piyasa etkisi ve yatırımcı akışı genel olarak nötr",
    },
}

# The named archetypes classify_fund_archetype can return. The
# "{group} Dominant Fund" family is not listed, translate_archetype builds it
# from GROUP_LABELS_TR so that it tracks the asset group map.
ARCHETYPE_TRANSLATIONS = {
    "tr": {
        "Money Market Fund": "Para Piyasası Fonu",
        "Domestic Equity Fund": "Yerli Hisse Senedi Fonu",
        "Foreign Equity Fund": "Yabancı Hisse Senedi Fonu",
        "Domestic Fixed-Income Fund": "Yerli Sabit Getirili Fon",
        "Foreign Fixed-Income Fund": "Yabancı Sabit Getirili Fon",
        "Fixed-Income Fund": "Sabit Getirili Fon",
        "FX / Eurobond Fixed-Income Fund": "Döviz / Eurobond Sabit Getirili Fon",
        "Domestic Fixed-Income Dominant Multi-Asset Fund": "Yerli Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Foreign Fixed-Income Dominant Multi-Asset Fund": "Yabancı Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Fixed-Income Dominant Multi-Asset Fund": "Sabit Getirili Ağırlıklı Çok Varlıklı Fon",
        "Multi-Asset / Mixed Allocation Fund": "Çok Varlıklı / Karma Dağılımlı Fon",
        "Gold / Precious Metals Fund": "Altın / Kıymetli Maden Fonu",
        "Fund Allocation Dominant Fund": "Fon Sepeti Ağırlıklı Fon",
        "Unknown Fund Type": "Bilinmeyen Fon Türü",
    }
}
ARCHETYPE_TRANSLATIONS["en"] = {key: key for key in ARCHETYPE_TRANSLATIONS["tr"]}

# classify_flow_regime_v2 composes its label from a magnitude and a participant
# clause. Turkish puts the participant clause first, so the phrases cannot be
# assembled in the same order; the whole set is generated from the same pieces
# the engine itself uses, which keeps the two in step if a magnitude is added.
FLOW_MAGNITUDE_TRANSLATIONS_TR = {
    "Neutral / negligible": "nötr / ihmal edilebilir",
    "Small": "küçük",
    "Moderate": "ılımlı",
    "Strong": "güçlü",
    "Unknown": "bilinmeyen",
}

# English clause -> Turkish phrase, with {magnitude} where the magnitude goes
FLOW_REGIME_CLAUSES_TR = {
    "net inflow with participant growth": "katılımcı artışıyla {magnitude} net giriş",
    "net inflow without participant growth": "katılımcı artışı olmadan {magnitude} net giriş",
    "net inflow with stable participant count": "katılımcı sayısı sabitken {magnitude} net giriş",
    "net outflow with participant decline": "katılımcı azalışıyla {magnitude} net çıkış",
    "net outflow despite participant growth": "katılımcı artışına rağmen {magnitude} net çıkış",
    "net outflow with stable participant count": "katılımcı sayısı sabitken {magnitude} net çıkış",
}

# The regimes that carry no magnitude
FLOW_REGIME_STANDALONE_TR = {
    "Neutral flow with participant growth": "Katılımcı artışıyla nötr akış",
    "Neutral flow with participant decline": "Katılımcı azalışıyla nötr akış",
    "Neutral flow regime": "Nötr akış rejimi",
    "Unknown flow regime": "Bilinmeyen akış rejimi",
}


def _build_flow_regime_translations() -> dict:
    turkish = dict(FLOW_REGIME_STANDALONE_TR)
    for magnitude, magnitude_tr in FLOW_MAGNITUDE_TRANSLATIONS_TR.items():
        for clause, clause_tr in FLOW_REGIME_CLAUSES_TR.items():
            phrase = clause_tr.format(magnitude=magnitude_tr)
            turkish[f"{magnitude} {clause}"] = phrase[0].upper() + phrase[1:]
    return {"en": {key: key for key in turkish}, "tr": turkish}


FLOW_REGIME_TRANSLATIONS = _build_flow_regime_translations()


def report_label(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Return a localized report label.
    """
    language = normalize_language(language)
    return REPORT_LABELS[language].get(key, REPORT_LABELS["en"].get(key, key))


def translate_quadrant_name(quadrant: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate market-flow quadrant labels for report output.
    """
    language = normalize_language(language)
    return QUADRANT_TRANSLATIONS[language].get(quadrant, quadrant)


def translate_dominance_strength(strength: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate dominance strength labels for report output.
    """
    language = normalize_language(language)
    return DOMINANCE_TRANSLATIONS[language].get(strength, strength)


def translate_archetype(archetype: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a v1 archetype label.

    ``classify_fund_archetype`` returns either one of the named archetypes or,
    when a single asset group dominates, ``f"{group} Dominant Fund"`` built from
    the broad asset group map. The second family is translated from the group
    labels rather than being listed here, so a new asset group is covered the
    moment it is added to the map.
    """
    language = normalize_language(language)
    if language == "en" or not isinstance(archetype, str):
        return archetype

    if archetype in ARCHETYPE_TRANSLATIONS[language]:
        return ARCHETYPE_TRANSLATIONS[language][archetype]

    if archetype.endswith(" Dominant Fund"):
        group = archetype[: -len(" Dominant Fund")]
        translated = GROUP_LABELS_TR.get(group)
        if translated:
            return f"{translated} Ağırlıklı Fon"

    return archetype


def translate_flow_regime(regime: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a flow regime label.
    """
    language = normalize_language(language)
    return FLOW_REGIME_TRANSLATIONS[language].get(regime, regime)


def get_quadrant_pattern_message(quadrant: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Return a localized natural-language explanation for a market-flow quadrant.
    """
    language = normalize_language(language)
    fallback = QUADRANT_PATTERN_MESSAGES["en"].get(
        quadrant,
        "the market-flow profile is mixed or neutral",
    )
    return QUADRANT_PATTERN_MESSAGES[language].get(quadrant, fallback)


def get_main_narrative_lines(
    universe_summary: dict,
    negative_market_share,
    positive_flow_share,
    language: str = DEFAULT_LANGUAGE,
) -> list:
    """
    Build localized main narrative bullets for the universe report.
    """
    language = normalize_language(language)
    total_net_flow = universe_summary["total_net_flow"]
    total_market_effect = universe_summary["total_market_effect"]

    if language == "tr":
        if total_net_flow > 0 and total_market_effect < 0:
            first_line = (
                "- Fon evreni pozitif net giriş aldı; ancak negatif piyasa performansı "
                "toplam AUM hareketine baskın geldi."
            )
        elif total_net_flow < 0 and total_market_effect < 0:
            first_line = (
                "- Fon evreni hem net çıkış hem de negatif piyasa performansı ile karşılaştı."
            )
        elif total_net_flow > 0 and total_market_effect > 0:
            first_line = (
                "- Fon evreni hem pozitif yatırımcı akışlarından hem de pozitif piyasa performansından destek aldı."
            )
        elif total_net_flow < 0 and total_market_effect > 0:
            first_line = (
                "- Fon evreni pozitif piyasa performansından destek aldı; ancak yatırımcı çıkışları toplam AUM etkisini sınırladı."
            )
        else:
            first_line = "- Fon evreni karma bir piyasa-akış profili sergiledi."

        return [
            first_line,
            f"- Negatif piyasa rejimleri fon evreni AUM'unun **{format_pct(negative_market_share)}** seviyesini temsil ediyor.",
            f"- Pozitif akış rejimleri fon evreni AUM'unun **{format_pct(positive_flow_share)}** seviyesini temsil ediyor.",
        ]

    if total_net_flow > 0 and total_market_effect < 0:
        first_line = (
            "- The fund universe received positive net inflows, "
            "but negative market performance dominated the total AUM movement."
        )
    elif total_net_flow < 0 and total_market_effect < 0:
        first_line = "- The fund universe faced both net outflows and negative market performance."
    elif total_net_flow > 0 and total_market_effect > 0:
        first_line = "- The fund universe benefited from both positive investor flows and positive market performance."
    elif total_net_flow < 0 and total_market_effect > 0:
        first_line = (
            "- The fund universe benefited from positive market performance, "
            "but investor outflows reduced the total AUM impact."
        )
    else:
        first_line = "- The fund universe showed a mixed market-flow profile."

    return [
        first_line,
        f"- Negative-market regimes represent **{format_pct(negative_market_share)}** of universe AUM.",
        f"- Positive-flow regimes represent **{format_pct(positive_flow_share)}** of universe AUM.",
    ]


def translate_markdown_report(markdown_text: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Backward-compatible placeholder.

    V4.1 builds bilingual Markdown directly in `market_report_to_markdown()` and
    `selected_funds_report_to_markdown()`. This function is retained for users
    who may still call it, but direct bilingual generation is preferred.
    """
    language = normalize_language(language)
    if language == "en":
        return markdown_text

    # Lightweight fallback for externally supplied Markdown.
    translated = markdown_text
    for key in [
        "market_report_title",
        "executive_summary",
        "main_narrative",
        "largest_archetypes",
        "market_flow_quadrants",
        "strongest_inflow_archetypes",
        "most_negative_market_effect",
        "dominant_regime_by_archetype",
        "interpretation_notes",
    ]:
        translated = translated.replace(
            REPORT_LABELS["en"][key],
            REPORT_LABELS["tr"][key],
        )
    return translated


def market_report_to_markdown(
    market_report: dict,
    lens_universe_df: Optional[pd.DataFrame] = None,
    top_n: int = 5,
    language: str = DEFAULT_LANGUAGE,
    classification_df: Optional[pd.DataFrame] = None,
    classification_fit_info=None,
) -> str:
    """
    Convert generate_market_narrative_report output into localized Markdown.

    If `lens_universe_df` is provided, a dominant market-flow regime section is
    added to the report.

    If `classification_df` is provided, the v2 allocation classification
    sections (asset classes, risk / currency / participation bands, style drift
    watchlist, model quality) are appended.
    """
    language = normalize_language(language)

    universe_summary = market_report["universe_summary"]
    archetype_summary = market_report["archetype_summary"]
    quadrant_summary = market_report["quadrant_summary"]

    total_aum_change_pct = (
        safe_divide(
            universe_summary["total_end_aum"],
            universe_summary["total_start_aum"],
        ) - 1
    )

    total_flow_pct = safe_divide(
        universe_summary["total_net_flow"],
        universe_summary["total_start_aum"],
    )

    total_market_pct = safe_divide(
        universe_summary["total_market_effect"],
        universe_summary["total_start_aum"],
    )

    negative_market_share = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Negative Market",
            na=False,
        )
    ]["start_aum_share"].sum()

    positive_flow_share = quadrant_summary[
        quadrant_summary["market_flow_quadrant"].str.contains(
            "Positive Flow",
            na=False,
        )
    ]["start_aum_share"].sum()

    lines = []

    lines.append(report_label("market_report_title", language))
    lines.append("")

    lines.append(report_label("executive_summary", language))
    lines.append("")
    lines.append(
        f"- {report_label('fund_universe_count', language)}: **{int(universe_summary['fund_count']):,}**"
    )
    lines.append(
        f"- {report_label('total_start_aum', language)}: **{format_try(universe_summary['total_start_aum'])}**"
    )
    lines.append(
        f"- {report_label('total_end_aum', language)}: **{format_try(universe_summary['total_end_aum'])}**"
    )
    lines.append(
        f"- {report_label('total_aum_change', language)}: **{format_pct(total_aum_change_pct)}**"
    )
    lines.append(
        f"- {report_label('total_net_flow', language)}: **{format_try(universe_summary['total_net_flow'])}** "
        f"(**{format_pct(total_flow_pct)}** {report_label('of_starting_aum', language)})"
    )
    lines.append(
        f"- {report_label('total_market_effect', language)}: **{format_try(universe_summary['total_market_effect'])}** "
        f"(**{format_pct(total_market_pct)}** {report_label('of_starting_aum', language)})"
    )
    lines.append("")

    lines.append(report_label("main_narrative", language))
    lines.append("")
    lines.extend(
        get_main_narrative_lines(
            universe_summary=universe_summary,
            negative_market_share=negative_market_share,
            positive_flow_share=positive_flow_share,
            language=language,
        )
    )
    lines.append("")

    lines.append(report_label("largest_archetypes", language))
    lines.append("")
    lines.append(
        f"| {report_label('archetype', language)} | {report_label('aum_share', language)} | "
        f"{report_label('flow', language)} | {report_label('market_effect', language)} | "
        f"{report_label('aum_change', language)} |"
    )
    lines.append("|---|---:|---:|---:|---:|")

    for _, row in archetype_summary.head(top_n).iterrows():
        lines.append(
            f"| {row['archetype']} "
            f"| {format_pct(row['start_aum_share'])} "
            f"| {format_pct(row['weighted_flow_pct'])} "
            f"| {format_pct(row['weighted_market_effect_pct'])} "
            f"| {format_pct(row['weighted_aum_change_pct'])} |"
        )

    lines.append("")

    lines.append(report_label("market_flow_quadrants", language))
    lines.append("")
    lines.append(
        f"| {report_label('quadrant', language)} | {report_label('aum_share', language)} | "
        f"{report_label('flow', language)} | {report_label('market_effect', language)} | "
        f"{report_label('aum_change', language)} | {report_label('fund_count', language)} |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")

    for _, row in quadrant_summary.head(top_n).iterrows():
        lines.append(
            f"| {translate_quadrant_name(row['market_flow_quadrant'], language)} "
            f"| {format_pct(row['start_aum_share'])} "
            f"| {format_pct(row['weighted_flow_pct'])} "
            f"| {format_pct(row['weighted_market_effect_pct'])} "
            f"| {format_pct(row['weighted_aum_change_pct'])} "
            f"| {int(row['fund_count'])} |"
        )

    lines.append("")

    lines.append(report_label("strongest_inflow_archetypes", language))
    lines.append("")
    lines.append(
        f"| {report_label('archetype', language)} | {report_label('weighted_flow', language)} | "
        f"{report_label('market_effect', language)} | {report_label('aum_share', language)} |"
    )
    lines.append("|---|---:|---:|---:|")

    strongest_inflows = archetype_summary.sort_values(
        "weighted_flow_pct",
        ascending=False,
    ).head(top_n)

    for _, row in strongest_inflows.iterrows():
        lines.append(
            f"| {row['archetype']} "
            f"| {format_pct(row['weighted_flow_pct'])} "
            f"| {format_pct(row['weighted_market_effect_pct'])} "
            f"| {format_pct(row['start_aum_share'])} |"
        )

    lines.append("")

    lines.append(report_label("most_negative_market_effect", language))
    lines.append("")
    lines.append(
        f"| {report_label('archetype', language)} | {report_label('market_effect', language)} | "
        f"{report_label('flow', language)} | {report_label('aum_share', language)} |"
    )
    lines.append("|---|---:|---:|---:|")

    weakest_market = archetype_summary.sort_values(
        "weighted_market_effect_pct",
        ascending=True,
    ).head(top_n)

    for _, row in weakest_market.iterrows():
        lines.append(
            f"| {row['archetype']} "
            f"| {format_pct(row['weighted_market_effect_pct'])} "
            f"| {format_pct(row['weighted_flow_pct'])} "
            f"| {format_pct(row['start_aum_share'])} |"
        )

    if lens_universe_df is not None:
        dominant_quadrant_df = summarize_dominant_quadrant_by_archetype(
            lens_universe_df
        )

        archetype_insights_df = generate_archetype_insights(
            dominant_quadrant_df,
            top_n=top_n,
            language=language,
        )

        lines.append("")
        lines.append(report_label("dominant_regime_by_archetype", language))
        lines.append("")
        lines.append(
            f"| {report_label('archetype', language)} | {report_label('dominant_regime', language)} | "
            f"{report_label('aum_share_in_regime', language)} | {report_label('strength', language)} | "
            f"{report_label('insight', language)} |"
        )
        lines.append("|---|---|---:|---|---|")

        for _, row in archetype_insights_df.iterrows():
            lines.append(
                f"| {row['archetype']} "
                f"| {row['dominant_quadrant_label']} "
                f"| {format_pct(row['dominant_quadrant_share'])} "
                f"| {row['dominance_strength_label']} "
                f"| {row['insight']} |"
            )

    if classification_df is not None and not classification_df.empty:
        lines.append("")
        classification_lines = build_classification_sections(
            classification_df,
            fit_info=classification_fit_info,
            language=language,
            top_n=top_n,
            include_notes=False,
        )
        # Sections end with a blank line of their own; drop it so the notes
        # heading below is not preceded by two.
        while classification_lines and classification_lines[-1] == "":
            classification_lines.pop()
        lines.extend(classification_lines)

    lines.append("")
    lines.append(report_label("interpretation_notes", language))
    lines.append("")
    lines.append(f"- {report_label('note_flow', language)}")
    lines.append(f"- {report_label('note_market_effect', language)}")
    lines.append(f"- {report_label('note_aum_change', language)}")
    lines.append(f"- {report_label('note_dominant_regime', language)}")
    lines.append(f"- {report_label('note_strength', language)}")
    lines.append(f"- {report_label('note_lookthrough', language)}")

    if classification_df is not None and not classification_df.empty:
        lines.extend(f"- {line}" for line in classification_note_lines(language))

    return "\n".join(lines)


def save_markdown_report(markdown_text: str, file_path: str = "besfundlens_market_report.md") -> str:
    """
    Markdown raporu dosyaya kaydeder ve dosya yolunu döndürür.
    """
    with open(file_path, "w", encoding="utf-8") as report_file:
        report_file.write(markdown_text)

    return file_path



# ============================================================
# 12. V4 Public API Helpers
# ============================================================

def build_selected_funds_lens(
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    valid_only: bool = False,
    min_start_aum: float = UNIVERSE_MIN_START_AUM,
    add_segments: bool = True,
    add_quadrants: bool = True,
) -> pd.DataFrame:
    """
    Build a lens universe for a user-selected fund list.

    This is the recommended V4 entry point for selected-fund analysis.
    """
    selected_df = build_lens_universe(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
        fund_codes=fund_codes,
        valid_only=valid_only,
        min_start_aum=min_start_aum,
    )

    if selected_df.empty:
        return selected_df

    if add_segments:
        selected_df = add_universe_segments(selected_df)

    if add_quadrants:
        selected_df = add_market_flow_quadrant(selected_df)

    return selected_df


def compare_funds(
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    sort_by: Optional[str] = None,
    ascending: bool = False,
) -> pd.DataFrame:
    """
    Compare selected funds by archetype, return, flow, market effect, and participant change.

    Example:
        compare_funds(["AAJ", "MHD", "MEA"], lookback="1m")
    """
    comparison_df = build_selected_funds_lens(
        fund_codes=fund_codes,
        lookback=lookback,
        lookback_intervals=lookback_intervals,
        valid_only=False,
        add_segments=True,
        add_quadrants=True,
    )

    if comparison_df.empty:
        return comparison_df

    default_columns = [
        "fonKodu",
        "fonUnvan",
        "archetype",
        "top_asset_group",
        "top_asset_weight",
        "top_currency",
        "top_currency_weight",
        "lookthrough_weight",
        "cumulative_return",
        "flow_pct",
        "market_effect_pct",
        "aum_change_pct",
        "participant_change_pct",
        "flow_regime",
        "market_flow_quadrant",
        "start_aum",
        "end_aum",
        "start_participants",
        "end_participants",
    ]

    available_columns = [
        column for column in default_columns
        if column in comparison_df.columns
    ]

    comparison_df = comparison_df[available_columns].copy()

    if sort_by is not None and sort_by in comparison_df.columns:
        comparison_df = comparison_df.sort_values(
            sort_by,
            ascending=ascending,
        )

    return comparison_df.reset_index(drop=True)


def selected_funds_report_to_markdown(
    comparison_df: pd.DataFrame,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Convert compare_funds output into a compact localized Markdown report.
    """
    language = normalize_language(language)

    if comparison_df is None or comparison_df.empty:
        return (
            f"{report_label('selected_report_title', language)}\n\n"
            f"{report_label('no_selected_data', language)}"
        )

    lines = [
        report_label("selected_report_title", language),
        "",
        report_label("fund_comparison", language),
        "",
    ]
    lines.append(
        f"| {report_label('fund', language)} | {report_label('archetype', language)} | "
        f"{report_label('return', language)} | {report_label('flow', language)} | "
        f"{report_label('market_effect', language)} | {report_label('aum_change', language)} | "
        f"{report_label('participant_change', language)} | {report_label('regime', language)} |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")

    for _, row in comparison_df.iterrows():
        lines.append(
            f"| {row.get('fonKodu', 'N/A')} "
            f"| {row.get('archetype', 'N/A')} "
            f"| {format_pct(row.get('cumulative_return', np.nan))} "
            f"| {format_pct(row.get('flow_pct', np.nan))} "
            f"| {format_pct(row.get('market_effect_pct', np.nan))} "
            f"| {format_pct(row.get('aum_change_pct', np.nan))} "
            f"| {format_pct(row.get('participant_change_pct', np.nan))} "
            f"| {translate_quadrant_name(row.get('market_flow_quadrant', 'N/A'), language)} |"
        )

    return "\n".join(lines)


def generate_selected_funds_report(
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """
    End-to-end selected fund analysis helper.

    Returns:
        {
            "comparison_df": DataFrame,
            "markdown": str,
            "lookback_intervals": int,
        }
    """
    resolved_lookback = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    comparison_df = compare_funds(
        fund_codes=fund_codes,
        lookback=resolved_lookback,
        lookback_intervals=resolved_lookback,
    )

    markdown = selected_funds_report_to_markdown(
        comparison_df,
        language=language,
    )

    return {
        "comparison_df": comparison_df,
        "markdown": markdown,
        "lookback_intervals": resolved_lookback,
    }


def run_universe_analysis(
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    fund_codes: Optional[Sequence[str]] = None,
    valid_only: bool = True,
    language: str = DEFAULT_LANGUAGE,
    top_n: int = 10,
    classify: bool = True,
    classification_config=None,
    classification_model_path=None,
    fit_classifier: bool = True,
    save_classifier_to=None,
) -> dict:
    """
    Convenience entry point for universe or selected-universe analysis.

    Classification (v2)
    -------------------
    With ``classify=True`` the v2 allocation classification layer runs over the
    same lookback window and its columns are merged onto the lens universe
    table. Pass ``classification_model_path`` (and ``fit_classifier=False``) to
    reuse a previously fitted model so class names stay comparable across
    reporting periods.

    The legacy rule-based ``archetype`` column is unaffected and is also copied
    to ``legacy_archetype``.
    """
    resolved_lookback = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    lens_universe = build_lens_universe(
        lookback_intervals=resolved_lookback,
        fund_codes=fund_codes,
        valid_only=valid_only,
    )

    if not lens_universe.empty:
        lens_universe = add_universe_segments(lens_universe)
        lens_universe = add_market_flow_quadrant(lens_universe)
        lens_universe["legacy_archetype"] = lens_universe["archetype"]

    classification_df = None
    classification_result = None

    if classify:
        classification_result = run_allocation_classification(
            lookback_intervals=resolved_lookback,
            fund_codes=fund_codes,
            config=classification_config,
            model_path=classification_model_path,
            fit=fit_classifier,
            save_model_to=save_classifier_to,
        )
        classification_df = classification_result["classification_df"]
        lens_universe = merge_classification(lens_universe, classification_df)

    market_report = generate_market_narrative_report(
        lens_universe,
        top_n=top_n,
        verbose=False,
    )

    markdown = market_report_to_markdown(
        market_report,
        lens_universe_df=lens_universe,
        top_n=top_n,
        language=language,
        classification_df=(
            lens_universe if classification_df is not None else None
        ),
        classification_fit_info=(
            classification_result["fit_info"] if classification_result else None
        ),
    )

    return {
        "lens_universe_df": lens_universe,
        "market_report": market_report,
        "markdown": markdown,
        "lookback_intervals": resolved_lookback,
        "classification_df": classification_df,
        "classification_model": (
            classification_result["model"] if classification_result else None
        ),
        "classification_fit_info": (
            classification_result["fit_info"] if classification_result else None
        ),
    }


def run_allocation_classification(
    lookback: Optional[Union[str, int]] = None,
    lookback_intervals: int = 20,
    fund_codes: Optional[Sequence[str]] = None,
    config=None,
    model_path=None,
    fit: bool = True,
    save_model_to=None,
) -> dict:
    """
    Run the v2 allocation classifier against the initialized engine panel.

    Thin wrapper over :func:`besfundlens.classification.classify_universe` that
    supplies the engine's DNA panel and asset metadata table.
    """
    require_initialized()

    resolved_lookback = resolve_lookback_intervals(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
    )

    panel = df_panel_dna
    codes = normalize_fund_codes(fund_codes)

    if codes is not None:
        panel = panel[panel["fonKodu"].isin(codes)]

    return classify_universe(
        panel_df=panel,
        asset_meta_df=asset_meta_df,
        lookback=None,
        lookback_intervals=resolved_lookback,
        config=config or DEFAULT_CLASSIFICATION_CONFIG,
        model_path=model_path,
        fit=fit,
        save_model_to=save_model_to,
    )


def merge_classification(
    lens_universe_df: pd.DataFrame,
    classification_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach classification columns to a lens universe table on ``fonKodu``.

    Columns the lens table already owns (``fonUnvan`` and friends) are dropped
    from the classification side so the merge does not create ``_x`` / ``_y``
    suffixes.
    """
    if lens_universe_df.empty or classification_df is None or classification_df.empty:
        return lens_universe_df

    overlapping = set(lens_universe_df.columns) - {"fonKodu"}
    new_columns = [
        col for col in classification_df.columns
        if col == "fonKodu" or col not in overlapping
    ]

    return lens_universe_df.merge(
        classification_df[new_columns],
        on="fonKodu",
        how="left",
    )


# ============================================================
# 13. Engine Initialization (Repo-Safe)
# ============================================================

# The original research notebook/script used a local SQLite path at import time.
# The public repo version is import-safe: users initialize the engine explicitly
# with DataFrames loaded from API, SQLite, CSV, Parquet, or any compatible source.
df_panel = None
df_genel_clean = None
df_dagilim_clean = None
asset_cols = None
panel_diagnostics = None
asset_meta_df = None
asset_validation = None
df_panel_dna = None
dna_cols = None
dna_broad_cols = None
dna_scope_cols = None
dna_currency_cols = None


def initialize_engine(
    df_genel_input: pd.DataFrame,
    df_dagilim_input: pd.DataFrame,
    verbose: bool = SHOW_STARTUP_DIAGNOSTICS,
) -> dict:
    """
    Initialize besFundLens analytics engine from two source DataFrames.

    Parameters
    ----------
    df_genel_input:
        General fund information table. Expected to include at least
        ``fonKodu``, ``fonUnvan``, ``tarih``, ``fiyat``, ``tedPaySayisi``,
        ``kisiSayisi`` and ``portfoyBuyukluk`` columns.
    df_dagilim_input:
        Fund allocation table. Expected to include ``fonKodu``, ``fonUnvan``,
        ``tarih`` and TEFAS/Fonturkey allocation columns.
    verbose:
        Print data preparation diagnostics.

    Returns
    -------
    dict
        Engine state references and diagnostics.
    """
    global df_panel, df_genel_clean, df_dagilim_clean, asset_cols, panel_diagnostics
    global asset_meta_df, asset_validation, df_panel_dna, dna_cols
    global dna_broad_cols, dna_scope_cols, dna_currency_cols

    if df_genel_input is None or df_dagilim_input is None:
        raise ValueError("df_genel_input and df_dagilim_input must be provided.")

    if df_genel_input.empty:
        raise ValueError("df_genel_input is empty.")

    if df_dagilim_input.empty:
        raise ValueError("df_dagilim_input is empty.")

    df_panel, df_genel_clean, df_dagilim_clean, asset_cols, panel_diagnostics = prepare_main_panel(
        df_genel=df_genel_input,
        df_dagilim=df_dagilim_input,
        verbose=verbose,
    )

    asset_meta_df = build_asset_metadata(asset_cols=asset_cols)
    asset_validation = validate_asset_metadata(asset_meta_df, asset_cols)

    df_panel_dna, dna_cols = build_dna_panel(
        panel_df=df_panel,
        asset_meta_df=asset_meta_df,
    )

    dna_broad_cols = dna_cols["broad"]
    dna_scope_cols = dna_cols["scope"]
    dna_currency_cols = dna_cols["currency"]

    df_panel_dna = add_flow_features(df_panel_dna)

    return {
        "df_panel": df_panel,
        "df_genel_clean": df_genel_clean,
        "df_dagilim_clean": df_dagilim_clean,
        "asset_cols": asset_cols,
        "panel_diagnostics": panel_diagnostics,
        "asset_meta_df": asset_meta_df,
        "asset_validation": asset_validation,
        "df_panel_dna": df_panel_dna,
        "dna_cols": dna_cols,
    }


def is_engine_initialized() -> bool:
    """Return True when the global analytics panel has been initialized."""
    return df_panel_dna is not None


def require_initialized() -> None:
    """Raise a clear error if analytics functions are called before initialization."""
    if not is_engine_initialized():
        raise RuntimeError(
            "besFundLens engine is not initialized. Call initialize_engine(df_genel, df_dagilim) "
            "or use a workflow helper such as run_universe_analysis_from_sqlite()."
        )


def run_universe_analysis_from_dataframes(
    df_genel_input: pd.DataFrame,
    df_dagilim_input: pd.DataFrame,
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    fund_codes: Optional[Sequence[str]] = None,
    valid_only: bool = True,
    language: str = DEFAULT_LANGUAGE,
    top_n: int = 10,
    verbose: bool = False,
) -> dict:
    """Initialize the engine from DataFrames and run universe analysis."""
    initialize_engine(df_genel_input, df_dagilim_input, verbose=verbose)
    return run_universe_analysis(
        lookback=lookback,
        lookback_intervals=lookback_intervals,
        fund_codes=fund_codes,
        valid_only=valid_only,
        language=language,
        top_n=top_n,
    )


def compare_funds_from_dataframes(
    df_genel_input: pd.DataFrame,
    df_dagilim_input: pd.DataFrame,
    fund_codes: Sequence[str],
    lookback: Optional[Union[str, int]] = "1m",
    lookback_intervals: int = 20,
    sort_by: Optional[str] = None,
    ascending: bool = False,
    verbose: bool = False,
) -> pd.DataFrame:
    """Initialize the engine from DataFrames and compare selected funds."""
    initialize_engine(df_genel_input, df_dagilim_input, verbose=verbose)
    return compare_funds(
        fund_codes=fund_codes,
        lookback=lookback,
        lookback_intervals=lookback_intervals,
        sort_by=sort_by,
        ascending=ascending,
    )

