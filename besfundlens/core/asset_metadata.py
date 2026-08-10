"""
Asset metadata and Fund DNA aggregation.

TEFAS/Fonturkey publishes fund allocations as one percentage column per
instrument code. This module maps those codes onto economic groupings
(broad asset group, market scope, currency exposure) and aggregates the raw
allocation columns into Fund DNA columns.

Moved out of ``besfundlens.core.engine`` so that ``besfundlens.classification``
can build its own feature spaces from the same metadata without importing the
engine. ``engine`` re-exports every public name defined here.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from besfundlens.core.utils import make_safe_col_name


# ============================================================
# Asset metadata maps
# ============================================================

asset_name_tr = {'bpp': 'Borsa İstanbul Para Piyasası (%)',
 'hs': 'Hisse Senedi (%)',
 'dt': 'Devlet Tahvili (%)',
 'hb': 'Hazine Bonosu (%)',
 'kibd': 'Döviz Cinsi Kamu İç Borçlanma Araçları (%)',
 'fb': 'Finansman Bonosu (%)',
 'ost': 'Özel Sektör Tahvili (%)',
 'vdm': 'Varlığa Dayalı Menkul Kıymetler (%)',
 'gas': 'Gayrı Menkul Sertifikası (%)',
 'gyy': 'Gayrimenkul Yatırımları (%)',
 'gsyy': 'Girişim Sermayesi Yatırımları (%)',
 'kba': 'Kamu Dış Borçlanma Araçları (%)',
 'osdb': 'Özel Sektör Dış Borçlanma Araçları (%)',
 'tpp': 'Takasbank Para Piyasası (%)',
 'kkstl': 'Kamu Kira Sertifikaları (TL) (%)',
 'kksd': 'Kamu Kira Sertifikaları (Döviz) (%)',
 'osks': 'Özel Sektör Kira Sertifikaları (%)',
 'kksyd': 'Kamu Yurt Dışı Kira Sertifikaları (%)',
 'oksyd': 'Özel Sektör Yurt Dışı Kira Sertifikaları (%)',
 'vmtl': 'Mevduat (TL) (%)',
 'vmd': 'Mevduat (Döviz) (%)',
 'khtl': 'Katılma Hesabı (TL) (%)',
 'khd': 'Katılma Hesabı (Döviz) (%)',
 'khau': 'Katılma Hesabı (Altın) (%)',
 'r': 'Repo (%)',
 'tr': 'Ters-Repo (%)',
 'btaa': 'BİST Taahhütlü İşlem Pazarı Alım (%)',
 'btas': 'BİST Taahhütlü İşlem Pazarı Satım (%)',
 'km': 'Kıymetli Madenler (%)',
 'kmbyf': 'Kıymetli Madenler Cinsinden BYF (%)',
 'kmkba': 'Kıymetli Madenler Cinsinden İhraç Edilen Kamu Borçlanma Araçları (%)',
 'kmkks': 'Kıymetli Madenler Cinsinden İhraç Edilen Kamu Kira Sertifikaları (%)',
 'ybkb': 'Yabancı Kamu Borçlanma Araçları (%)',
 'ybosb': 'Yabancı Özel Sektör Borçlanma Araçları (%)',
 'yhs': 'Yabancı Hisse Senedi (%)',
 'ybyf': 'Yabancı Borsa Yatırım Fonları (%)',
 'yyf': 'Yatırım Fonları Katılma Payları (%)',
 'byf': 'Borsa Yatırım Fonları Katılma Payları (%)',
 'gykb': 'Gayrimenkul Yatırım Fonları Katılma Payları (%)',
 'gsykb': 'Girişim Sermayesi Yatırım Fonları Katılma Payları (%)',
 'db': 'Döviz Ödemeli Bono (%)',
 'dot': 'Dövize Ödemeli Tahvil (%)',
 'bb': 'Banka Bonosu (%)',
 'eut': 'Eurobonds (%)',
 'kks': 'Kamu Kira Sertifikaları (%)',
 'vm': 'Vadeli Mevduat (%)',
 'vmau': 'Mevduat (Altın) (%)',
 'kh': 'Katılım Hesabı (%)',
 'ymk': 'Yabancı Menkul Kıymet (%)',
 'yba': 'Yabancı Borçlanma Aracı (%)',
 'fkb': 'Fon Katılma Belgesi (%)',
 't': 'Türev Araçları (%)',
 'vint': 'Vadeli İşlemler Nakit Teminatları (%)',
 'd': 'Diğer (%)'}

asset_name_en = {'bpp': 'Borsa Istanbul Money Market (%)',
 'hs': 'Stock (%)',
 'dt': 'Government Bond (%)',
 'hb': 'Treasury Bill (%)',
 'kibd': 'Government Currency Debt Securities (%)',
 'fb': 'Commercial Paper (%)',
 'ost': 'Private Sector Bond (%)',
 'vdm': 'Asset-Backed Securities (%)',
 'gas': 'Real Estate Certificate (%)',
 'gyy': 'Real Estate Investments (%)',
 'gsyy': 'Venture Capital Investments (%)',
 'kba': 'Government Bonds and Bills (FX) (%)',
 'osdb': 'International Corporate Debt Securities (%)',
 'tpp': 'Takasbank Money Market (%)',
 'kkstl': 'Government Lease Certificate (Turkish Lira) (%)',
 'kksd': 'Government Lease Certificate (Foreign Currency) (%)',
 'osks': 'Private Sector Lease Certificates (%)',
 'kksyd': 'International Government Lease Certificates (%)',
 'oksyd': 'International Corporate Lease Certificates (%)',
 'vmtl': 'Deposit Account (Turkish Lira) (%)',
 'vmd': 'Deposit Account (Foreign Currency) (%)',
 'khtl': 'Participation Account (Turkish Lira) (%)',
 'khd': 'Participation Account (Foreign Currency) (%)',
 'khau': 'Participation Account (Gold) (%)',
 'r': 'Repo (%)',
 'tr': 'Reverse-Repo (%)',
 'btaa': 'BIST Committed Transactions Market Buy (%)',
 'btas': 'BIST Committed Transactions Market Sell (%)',
 'km': 'Precious Metals (%)',
 'kmbyf': 'Exchange Traded Fund Issued in Precious Metals (%)',
 'kmkba': 'Government Debt Securities Issued in Precious Metal (%)',
 'kmkks': 'Government Lease Certificates Issued in Precious Metal (%)',
 'ybkb': 'International Government Debt Securities (%)',
 'ybosb': 'International Corporate Debt Securities (%)',
 'yhs': 'Foreign Equity (%)',
 'ybyf': 'International Exchange Traded Fund (%)',
 'yyf': 'Investment Funds Participation Share (%)',
 'byf': 'Exchange Traded Fund Participation Share (%)',
 'gykb': 'Real Estate Investment Fund Participation Share (%)',
 'gsykb': 'Venture Capital Investment Fund Participation Share (%)',
 'db': 'FX Payable Bills (%)',
 'dot': 'Foreign Currency Bills (%)',
 'bb': 'Bank Bills (%)',
 'eut': 'Eurobonds (%)',
 'kks': 'Government Lease Certificates (%)',
 'vm': 'Term Deposit (%)',
 'vmau': 'Deposit Account (Gold) (%)',
 'kh': 'Participation Account (%)',
 'ymk': 'Foreign Securities (%)',
 'yba': 'Foreign Debt Instruments (%)',
 'fkb': 'Fund Participation Certificate (%)',
 't': 'Derivatives (%)',
 'vint': 'Futures Contract Cash Collateral (%)',
 'd': 'Other (%)'}

asset_group_map = {'bpp': 'Money Market',
 'tpp': 'Money Market',
 'r': 'Money Market',
 'tr': 'Money Market',
 'btaa': 'Money Market',
 'btas': 'Money Market',
 'vint': 'Derivative Collateral',
 'hs': 'Equity',
 'yhs': 'Foreign Equity',
 'dt': 'Government Fixed Income',
 'hb': 'Government Fixed Income',
 'kibd': 'Government Fixed Income FX',
 'kba': 'Government Fixed Income FX',
 'ybkb': 'Foreign Government Fixed Income',
 'yba': 'Foreign Government Fixed Income',
 'eut': 'Eurobond',
 'db': 'Government Fixed Income FX',
 'dot': 'Government Fixed Income FX',
 'fb': 'Private Sector Fixed Income',
 'ost': 'Private Sector Fixed Income',
 'bb': 'Private Sector Fixed Income',
 'vdm': 'Structured Fixed Income',
 'osdb': 'Foreign Private Sector Fixed Income',
 'ybosb': 'Foreign Private Sector Fixed Income',
 'kkstl': 'Lease Certificate',
 'kksd': 'Lease Certificate FX',
 'osks': 'Private Sector Lease Certificate',
 'kksyd': 'Foreign Lease Certificate',
 'oksyd': 'Foreign Lease Certificate',
 'kks': 'Lease Certificate',
 'vmtl': 'Deposit',
 'vmd': 'FX Deposit',
 'vm': 'Deposit',
 'vmau': 'Gold Deposit',
 'khtl': 'Participation Account',
 'khd': 'FX Participation Account',
 'khau': 'Gold Participation Account',
 'kh': 'Participation Account',
 'km': 'Precious Metals',
 'kmbyf': 'Precious Metals',
 'kmkba': 'Precious Metals Linked Debt',
 'kmkks': 'Precious Metals Linked Lease Certificate',
 'yyf': 'Investment Fund',
 'byf': 'ETF',
 'ybyf': 'Foreign ETF',
 'fkb': 'Investment Fund',
 'gykb': 'Real Estate Fund',
 'gsykb': 'Venture Capital Fund',
 'gas': 'Real Estate',
 'gyy': 'Real Estate',
 'gsyy': 'Venture Capital',
 'ymk': 'Foreign Securities',
 't': 'Derivatives',
 'd': 'Other'}

broad_asset_group_map = {'hs': 'Equity',
 'yhs': 'Foreign Equity',
 'dt': 'Fixed Income',
 'hb': 'Fixed Income',
 'kibd': 'Fixed Income',
 'kba': 'Fixed Income',
 'ybkb': 'Fixed Income',
 'yba': 'Fixed Income',
 'eut': 'Fixed Income',
 'db': 'Fixed Income',
 'dot': 'Fixed Income',
 'fb': 'Fixed Income',
 'ost': 'Fixed Income',
 'bb': 'Fixed Income',
 'vdm': 'Fixed Income',
 'osdb': 'Fixed Income',
 'ybosb': 'Fixed Income',
 'kkstl': 'Lease Certificates',
 'kksd': 'Lease Certificates',
 'osks': 'Lease Certificates',
 'kksyd': 'Lease Certificates',
 'oksyd': 'Lease Certificates',
 'kks': 'Lease Certificates',
 'bpp': 'Money Market',
 'tpp': 'Money Market',
 'r': 'Money Market',
 'tr': 'Money Market',
 'btaa': 'Money Market',
 'btas': 'Money Market',
 'vint': 'Money Market / Collateral',
 'vmtl': 'Deposit',
 'vmd': 'Deposit',
 'vm': 'Deposit',
 'vmau': 'Deposit',
 'khtl': 'Participation Account',
 'khd': 'Participation Account',
 'khau': 'Participation Account',
 'kh': 'Participation Account',
 'km': 'Precious Metals',
 'kmbyf': 'Precious Metals',
 'kmkba': 'Precious Metals',
 'kmkks': 'Precious Metals',
 'yyf': 'Fund',
 'byf': 'ETF',
 'ybyf': 'Foreign ETF',
 'fkb': 'Fund',
 'gykb': 'Real Estate / Alternative',
 'gsykb': 'Venture Capital / Alternative',
 'gas': 'Real Estate / Alternative',
 'gyy': 'Real Estate / Alternative',
 'gsyy': 'Venture Capital / Alternative',
 't': 'Derivatives',
 'ymk': 'Foreign Securities',
 'd': 'Other'}

market_scope_map = {'bpp': 'Domestic',
 'hs': 'Domestic',
 'dt': 'Domestic',
 'hb': 'Domestic',
 'kibd': 'Domestic',
 'fb': 'Domestic',
 'ost': 'Domestic',
 'vdm': 'Domestic',
 'gas': 'Domestic',
 'gyy': 'Domestic',
 'gsyy': 'Domestic',
 'tpp': 'Domestic',
 'kkstl': 'Domestic',
 'kksd': 'Domestic',
 'osks': 'Domestic',
 'vmtl': 'Domestic',
 'vmd': 'Domestic',
 'khtl': 'Domestic',
 'khd': 'Domestic',
 'khau': 'Domestic',
 'r': 'Domestic',
 'tr': 'Domestic',
 'btaa': 'Domestic',
 'btas': 'Domestic',
 'bb': 'Domestic',
 'kks': 'Domestic',
 'vm': 'Domestic',
 'vmau': 'Domestic',
 'kh': 'Domestic',
 'kba': 'Foreign / International',
 'osdb': 'Foreign / International',
 'kksyd': 'Foreign / International',
 'oksyd': 'Foreign / International',
 'ybkb': 'Foreign / International',
 'ybosb': 'Foreign / International',
 'yhs': 'Foreign / International',
 'ybyf': 'Foreign / International',
 'ymk': 'Foreign / International',
 'yba': 'Foreign / International',
 'eut': 'Foreign / International',
 'db': 'Foreign / International',
 'dot': 'Foreign / International',
 'km': 'Commodity / Global Pricing',
 'kmbyf': 'Commodity / Global Pricing',
 'kmkba': 'Commodity / Global Pricing',
 'kmkks': 'Commodity / Global Pricing',
 'yyf': 'Look-through Required',
 'byf': 'Look-through Required',
 'gykb': 'Look-through Required',
 'gsykb': 'Look-through Required',
 'fkb': 'Look-through Required',
 'vint': 'Operational / Cash-like',
 't': 'Other / Unknown',
 'd': 'Other / Unknown'}

currency_exposure_map = {'bpp': 'TRY',
 'hs': 'TRY',
 'dt': 'TRY',
 'hb': 'TRY',
 'fb': 'TRY',
 'ost': 'TRY',
 'vdm': 'TRY',
 'gas': 'TRY',
 'gyy': 'TRY',
 'gsyy': 'TRY',
 'tpp': 'TRY',
 'kkstl': 'TRY',
 'osks': 'TRY',
 'vmtl': 'TRY',
 'khtl': 'TRY',
 'r': 'TRY',
 'tr': 'TRY',
 'btaa': 'TRY',
 'btas': 'TRY',
 'bb': 'TRY',
 'kks': 'TRY',
 'vm': 'TRY',
 'kh': 'TRY',
 'kibd': 'FX',
 'kba': 'FX',
 'osdb': 'FX',
 'kksd': 'FX',
 'kksyd': 'FX',
 'oksyd': 'FX',
 'vmd': 'FX',
 'khd': 'FX',
 'ybkb': 'FX',
 'ybosb': 'FX',
 'yhs': 'FX',
 'ybyf': 'FX',
 'ymk': 'FX',
 'yba': 'FX',
 'eut': 'FX',
 'db': 'FX',
 'dot': 'FX',
 'khau': 'Gold',
 'km': 'Gold',
 'kmbyf': 'Gold',
 'kmkba': 'Gold',
 'kmkks': 'Gold',
 'vmau': 'Gold',
 'yyf': 'Look-through Required',
 'byf': 'Look-through Required',
 'gykb': 'Look-through Required',
 'gsykb': 'Look-through Required',
 'fkb': 'Look-through Required',
 'vint': 'Operational / Collateral',
 't': 'Mixed / Unknown',
 'd': 'Other / Unknown'}


# ============================================================
# Metadata table builders
# ============================================================

def build_asset_metadata(asset_cols: Optional[list] = None) -> pd.DataFrame:
    """
    Varlık kodlarını ekonomik metadata tablosuna dönüştürür.
    """
    asset_meta_df = pd.DataFrame({
        "asset_code": list(asset_name_tr.keys())
    })

    asset_meta_df["asset_name_tr"] = asset_meta_df["asset_code"].map(asset_name_tr)
    asset_meta_df["asset_name_en"] = asset_meta_df["asset_code"].map(asset_name_en)

    asset_meta_df["asset_name_tr_clean"] = (
        asset_meta_df["asset_name_tr"]
        .str.replace(r"\s*\(%\)\s*$", "", regex=True)
    )

    asset_meta_df["asset_name_en_clean"] = (
        asset_meta_df["asset_name_en"]
        .str.replace(r"\s*\(%\)\s*$", "", regex=True)
    )

    asset_meta_df["asset_group"] = asset_meta_df["asset_code"].map(asset_group_map)
    asset_meta_df["broad_asset_group"] = asset_meta_df["asset_code"].map(broad_asset_group_map)
    asset_meta_df["market_scope"] = asset_meta_df["asset_code"].map(market_scope_map)
    asset_meta_df["currency_exposure"] = asset_meta_df["asset_code"].map(currency_exposure_map)

    if asset_cols is not None:
        asset_meta_df["is_active_in_panel"] = asset_meta_df["asset_code"].isin(asset_cols)

    return asset_meta_df


def validate_asset_metadata(asset_meta_df: pd.DataFrame, asset_cols: list) -> dict:
    """
    Paneldeki varlık kodları ile metadata tablosunu karşılaştırır.
    """
    active_asset_codes = [
        code for code in asset_meta_df["asset_code"].tolist()
        if code in asset_cols
    ]

    inactive_asset_codes = [
        code for code in asset_meta_df["asset_code"].tolist()
        if code not in asset_cols
    ]

    missing_asset_names = sorted(
        set(asset_cols) - set(asset_meta_df["asset_code"])
    )

    unclassified_assets = asset_meta_df[
        asset_meta_df[
            ["asset_group", "broad_asset_group", "market_scope", "currency_exposure"]
        ].isna().any(axis=1)
    ].copy()

    return {
        "active_asset_codes": active_asset_codes,
        "inactive_asset_codes": inactive_asset_codes,
        "missing_asset_names": missing_asset_names,
        "unclassified_assets": unclassified_assets,
    }


# ============================================================
# DNA feature engineering
# ============================================================

def add_dna_columns(
    panel_df: pd.DataFrame,
    meta_df: pd.DataFrame,
    group_col: str,
    prefix: str,
):
    """
    panel_df içindeki varlık kolonlarını meta_df içindeki sınıflandırmaya göre toplar.

    Örnek:
    group_col='broad_asset_group', prefix='dna_broad'
    """
    result_df = panel_df.copy()

    valid_meta = meta_df[
        meta_df["asset_code"].isin(result_df.columns)
    ].copy()

    groups = sorted(valid_meta[group_col].dropna().unique())

    created_cols = []

    for group in groups:
        codes = valid_meta.loc[
            valid_meta[group_col].eq(group),
            "asset_code",
        ].tolist()

        col_name = f"{prefix}_{make_safe_col_name(group)}"

        result_df[col_name] = result_df[codes].sum(axis=1)
        created_cols.append(col_name)

    return result_df, created_cols


def build_dna_panel(
    panel_df: pd.DataFrame,
    asset_meta_df: pd.DataFrame,
):
    """
    Ana panele broad, scope ve currency DNA kolonlarını ekler.
    """
    df_panel_dna, dna_broad_cols = add_dna_columns(
        panel_df=panel_df,
        meta_df=asset_meta_df,
        group_col="broad_asset_group",
        prefix="dna_broad",
    )

    df_panel_dna, dna_scope_cols = add_dna_columns(
        panel_df=df_panel_dna,
        meta_df=asset_meta_df,
        group_col="market_scope",
        prefix="dna_scope",
    )

    df_panel_dna, dna_currency_cols = add_dna_columns(
        panel_df=df_panel_dna,
        meta_df=asset_meta_df,
        group_col="currency_exposure",
        prefix="dna_currency",
    )

    df_panel_dna["dna_broad_total"] = df_panel_dna[dna_broad_cols].sum(axis=1)
    df_panel_dna["dna_scope_total"] = df_panel_dna[dna_scope_cols].sum(axis=1)
    df_panel_dna["dna_currency_total"] = df_panel_dna[dna_currency_cols].sum(axis=1)

    dna_cols = {
        "broad": dna_broad_cols,
        "scope": dna_scope_cols,
        "currency": dna_currency_cols,
    }

    return df_panel_dna, dna_cols


# ============================================================
# DNA label helpers
# ============================================================

def clean_dna_label(col_name: str, prefix: str) -> str:
    """
    DNA kolon adını okunabilir etikete çevirir.

    Örnek:
    dna_broad_fixed_income          -> Fixed Income
    dna_currency_fx                 -> FX
    dna_scope_look_through_required -> Look-through Required
    """
    raw_label = col_name.replace(prefix + "_", "")

    label_overrides = {
        "try": "TRY",
        "fx": "FX",
        "etf": "ETF",
        "foreign_etf": "Foreign ETF",
        "foreign_equity": "Foreign Equity",
        "fixed_income": "Fixed Income",
        "foreign_securities": "Foreign Securities",
        "money_market": "Money Market",
        "money_market_collateral": "Money Market / Collateral",
        "precious_metals": "Precious Metals",
        "participation_account": "Participation Account",
        "lease_certificates": "Lease Certificates",
        "real_estate_alternative": "Real Estate / Alternative",
        "venture_capital_alternative": "Venture Capital / Alternative",
        "foreign_international": "Foreign / International",
        "commodity_global_pricing": "Commodity / Global Pricing",
        "look_through_required": "Look-through Required",
        "operational_cash_like": "Operational / Cash-like",
        "operational_collateral": "Operational / Collateral",
        "mixed_unknown": "Mixed / Unknown",
        "other_unknown": "Other / Unknown",
    }

    if raw_label in label_overrides:
        return label_overrides[raw_label]

    return raw_label.replace("_", " ").title()
