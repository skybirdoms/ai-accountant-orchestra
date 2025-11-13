import pandas as pd
import numpy as np
from tools.analysis.tax import compute_vat, load_rules


# ─────────────────────────────────────────────────────────────
# Test: compute_vat on DataFrame
# ─────────────────────────────────────────────────────────────

def test_df_basic_vat():
    df = pd.DataFrame([
        {"amount_gross": 100.0, "category": "Food"},
        {"amount_gross": 121.0, "category": "General"},
    ])

    rules = {
        "category_rates": {"Food": 0.09, "General": 0.21},
        "default_rate": 0.21,
        "kor_threshold": 0,  # KOR отключён
    }

    res = compute_vat(df, rules)

    # Проверяем столбцы
    assert "tax_amount" in res.columns
    assert "effective_rate" in res.columns

    # Проверяем расчёт VAT
    food_vat = 100 * 0.09 / 1.09
    general_vat = 121 * 0.21 / 1.21

    assert np.isclose(res.loc[0, "tax_amount"], food_vat)
    assert np.isclose(res.loc[1, "tax_amount"], general_vat)

    # Breakdown работает
    breakdown = res.attrs.get("vat_breakdown")
    assert breakdown["low"] > 0
    assert breakdown["high"] > 0


# ─────────────────────────────────────────────────────────────
# Test: compute_vat with summary dict
# ─────────────────────────────────────────────────────────────

def test_summary_basic():
    summary = {
        "gross_revenue": 123.0,
        "by_group": [
            {"key": "Food", "gross": 54.63},
            {"key": "General", "gross": 68.37},
        ],
    }

    rules = {
        "category_rates": {"Food": 0.09, "General": 0.21},
        "default_rate": 0.21,
        "kor_threshold": 0,
    }

    res = compute_vat(summary, rules)

    assert "by_group" in res

    fg = res["by_group"][0]
    gg = res["by_group"][1]

    assert "tax_amount" in fg
    assert "effective_rate" in fg
    assert "tax_amount" in gg
    assert "effective_rate" in gg

    assert np.isclose(fg["effective_rate"], 0.09)
    assert np.isclose(gg["effective_rate"], 0.21)


# ─────────────────────────────────────────────────────────────
# Test: load rules from YAML or JSON
# ─────────────────────────────────────────────────────────────

def test_load_rules_yaml(tmp_path):
    yml = tmp_path / "vat_rules.yaml"
    yml.write_text(
        "category_rates:\n  Food: 0.09\n  General: 0.21\ndefault_rate: 0.21\n",
        encoding="utf-8",
    )

    rules = load_rules(str(yml))
    assert rules["category_rates"]["Food"] == 0.09
    assert rules["default_rate"] == 0.21


# ─────────────────────────────────────────────────────────────
# Test: KOR should zero out VAT
# ─────────────────────────────────────────────────────────────

def test_kor_zero():
    df = pd.DataFrame([
        {"amount_gross": 100.0, "category": "Food"},
    ])

    rules = {
        "category_rates": {"Food": 0.09},
        "default_rate": 0.21,
        "kor_threshold": 20000,  # включаем KOR
    }

    res = compute_vat(df, rules)

    assert res.attrs["kor_applied"] is True
    assert float(res["tax_amount"].sum()) == 0.0
