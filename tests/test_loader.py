import pathlib
import pandas as pd
import numpy as np

from tools.data_io import loader as _loader

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "tx_minimal.csv"


def test_load_dataframe_required_columns():
    df = _loader.load_dataframe(str(FIXTURE))

    required = {"date", "description", "amount_gross", "vat_rate", "category"}
    assert required.issubset(df.columns), f"Отсутствуют колонки: {required - set(df.columns)}"


def test_load_dataframe_dtypes_basic():
    df = _loader.load_dataframe(str(FIXTURE))

    # 1) date — допускаем строковый тип, но проверяем, что парсится в datetime
    parsed = pd.to_datetime(df["date"], errors="raise", utc=False)
    assert len(parsed) == len(df)

    # 2) amount_gross — числовой
    assert pd.api.types.is_numeric_dtype(df["amount_gross"])

    # 3) vat_rate — может быть числовой или частично пустой
    assert pd.api.types.is_numeric_dtype(df["vat_rate"]) or df["vat_rate"].isna().any()

    # 4) description и category — строковые
    assert df["description"].dtype.kind in {"O", "U"}
    assert df["category"].dtype.kind in {"O", "U"}

