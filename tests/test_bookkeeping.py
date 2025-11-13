import pathlib
import pandas as pd

from tools.data_io import loader as _loader
from tools.analysis import bookkeeping as _bk

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "tx_minimal.csv"


def test_summarize_has_expected_keys():
    df = _loader.load_dataframe(str(FIXTURE))
    # Укажем groupby явно — подстроимся под текущее API
    result = _bk.summarize(df, groupby="category")

    for key in [
        "n_transactions",
        "gross_revenue",
        "net_revenue",
        "returns",
        "by_group",
    ]:
        assert key in result, f"Отсутствует ключ в summarize(..): {key}"


def test_grouping_by_month():
    df = _loader.load_dataframe(str(FIXTURE))

    out = _bk.summarize(df, groupby="month")
    assert "by_group" in out
    groups = {g.get("key") for g in out["by_group"]}

    # Должны быть хотя бы две группы — январь и февраль 2024
    assert any(str(g).startswith("2024-01") for g in groups)
    assert any(str(g).startswith("2024-02") for g in groups)
