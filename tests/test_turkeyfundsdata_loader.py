import pandas as pd
import pytest

from besfundlens.data.loaders import load_turkeyfundsdata_frame


def sample_frame():
    """
    A frame shaped the way turkeyfundsdata's tefas.get_fund_data returns one.

    Column names are upper cased, price and allocation arrive merged, and
    TEDPAYSAYISI is a fixed-point string because that script formats it for
    display before handing it back.
    """
    return pd.DataFrame(
        {
            "TARIH": pd.to_datetime(["2026-08-03", "2026-08-04"]),
            "FONKODU": ["AAL", "AAL"],
            "FONUNVAN": ["ATA PORTFÖY PARA PİYASASI (TL) FONU"] * 2,
            "FIYAT": [3.465327, 3.470112],
            "FIYAT_6DEC": ["3.465327", "3.470112"],
            "TEDPAYSAYISI": ["619148838.000000", "620000000.000000"],
            "KISISAYISI": [4581, 4590],
            "PORTFOYBUYUKLUK": [2145552900.64, 2151000000.00],
            "BORSABULTENFIYAT": [0.0, 0.0],
            "DT": [15.81, 15.90],
            "VMTL": [19.72, 19.60],
            "HS": [0.0, 0.0],
        }
    )


def test_splits_into_the_two_frames_the_engine_expects():
    df_general, df_allocation = load_turkeyfundsdata_frame(sample_frame())

    assert list(df_general.columns) == [
        "tarih",
        "fonKodu",
        "fonUnvan",
        "fiyat",
        "tedPaySayisi",
        "kisiSayisi",
        "portfoyBuyukluk",
        "borsaBultenFiyat",
    ]
    assert list(df_allocation.columns) == ["tarih", "fonKodu", "fonUnvan", "dt", "vmtl", "hs"]


def test_display_only_columns_are_dropped():
    df_general, df_allocation = load_turkeyfundsdata_frame(sample_frame())

    assert "FIYAT_6DEC" not in df_general.columns
    assert "fiyat_6dec" not in df_allocation.columns


def test_numeric_columns_are_numbers_not_strings():
    """The engine divides portfoyBuyukluk by tedPaySayisi, which arrives as a string."""
    df_general, df_allocation = load_turkeyfundsdata_frame(sample_frame())

    assert pd.api.types.is_numeric_dtype(df_general["tedPaySayisi"])
    assert pd.api.types.is_numeric_dtype(df_general["portfoyBuyukluk"])
    assert pd.api.types.is_numeric_dtype(df_allocation["dt"])
    assert df_general["tedPaySayisi"].iloc[0] == pytest.approx(619148838.0)


def test_dates_are_normalised_to_the_engines_format():
    df_general, _ = load_turkeyfundsdata_frame(sample_frame())

    assert df_general["tarih"].tolist() == ["2026-08-03", "2026-08-04"]


def test_rejects_a_frame_that_is_not_from_turkeyfundsdata():
    with pytest.raises(ValueError, match="Not a turkeyfundsdata frame"):
        load_turkeyfundsdata_frame(pd.DataFrame({"fonKodu": ["AAL"]}))
