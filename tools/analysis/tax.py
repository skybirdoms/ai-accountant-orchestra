from __future__ import annotations
from typing import Dict, Any, Union
import json
import os
import pandas as pd
import numpy as np
import yaml


# ─────────────────────────────────────────────────────────────
# ЗАГРУЗКА ПРАВИЛ
# ─────────────────────────────────────────────────────────────

def load_rules(path: str) -> Dict[str, Any]:
    """
    Загружает налоговые правила из YAML или JSON.
    Пример:
      default_rate: 0.21
      category_rates:
        Produce: 0.09
        Dairy: 0.09
        Electronics: 0.21
    """
    if not os.path.exists(path):
        raise ValueError(f"Rules file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in [".yml", ".yaml"]:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception as e:
        raise ValueError(f"Failed to read rules from '{path}': {e}")

    raise ValueError("Unsupported rules file extension. Use .yaml/.yml or .json.")


# ─────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _vat_from_gross(gross: float, rate: float) -> float:
    """VAT = gross * rate / (1 + rate)."""
    if rate <= 0:
        return 0.0
    return float(gross) * float(rate) / (1.0 + float(rate))


def _kor_applies(total_gross: float, rules: Dict[str, Any]) -> bool:
    """Проверка KOR-порога."""
    threshold = float((rules or {}).get("kor_threshold", np.inf))
    return total_gross < threshold


# ─────────────────────────────────────────────────────────────
# ОСНОВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────────────────────

def compute_vat(data: Union[pd.DataFrame, Dict[str, Any]], rules: Dict[str, Any]) -> Union[pd.DataFrame, Dict[str, Any]]:
    """
    Расширенная функция расчёта НДС для Нидерландов (2025).
    Поддерживает:
      - категории с разными ставками;
      - проверку KOR (порог 20 000 €);
      - формирование vat_breakdown {"low": ..., "high": ...}.
    """

    # === Ветка 1: DataFrame ===
    if isinstance(data, pd.DataFrame):
        df = data.copy()

        if "amount_gross" not in df.columns:
            df["tax_amount"] = 0.0
            df["vat"] = 0.0
            df.attrs["kor_applied"] = False
            df.attrs["vat_breakdown"] = {"low": 0.0, "high": 0.0}
            return df

        category_rates = (rules or {}).get("category_rates") or {}
        default_rate = float((rules or {}).get("default_rate", 0.21))

        def _rate_for_row(r):
            if pd.notna(r.get("vat_rate")):
                return float(r["vat_rate"])
            cat = str(r.get("category") or "")
            return float(category_rates.get(cat, default_rate))

        df["effective_rate"] = df.apply(_rate_for_row, axis=1)
        df["tax_amount"] = df.apply(lambda r: _vat_from_gross(r["amount_gross"], r["effective_rate"]), axis=1)
        df["vat"] = df["tax_amount"]

        total_gross = float(df["amount_gross"].sum())
        kor = _kor_applies(total_gross, rules)

        if kor:
            df["tax_amount"] = 0.0
            df["vat"] = 0.0

        # Разбивка low/high
        low_sum = float(df.loc[np.isclose(df["effective_rate"], 0.09), "tax_amount"].sum())
        high_sum = float(df.loc[np.isclose(df["effective_rate"], 0.21), "tax_amount"].sum())

        df.attrs["kor_applied"] = bool(kor)
        df.attrs["vat_breakdown"] = {"low": low_sum, "high": high_sum}

        return df

    # === Ветка 2: summary-словарь ===
    if isinstance(data, dict) and "by_group" in data:
        summary = dict(data)
        by_group = summary.get("by_group") or []
        total_gross = float(summary.get("gross_revenue", 0.0))

        kor = _kor_applies(total_gross, rules)
        category_rates = (rules or {}).get("category_rates") or {}
        default_rate = float((rules or {}).get("default_rate", 0.21))

        low_sum = high_sum = 0.0

        for g in by_group:
            cat = str(g.get("key") or "")
            gross = float(g.get("gross", 0.0))
            rate = float(category_rates.get(cat, default_rate))
            tax = 0.0 if kor else _vat_from_gross(gross, rate)

            g["effective_rate"] = rate
            g["tax_amount"] = tax

            if np.isclose(rate, 0.09):
                low_sum += tax
            elif np.isclose(rate, 0.21):
                high_sum += tax

        summary["kor_applied"] = bool(kor)
        summary["vat_breakdown"] = {"low": low_sum, "high": high_sum}
        summary["by_group"] = by_group

        return summary

    return data

