# tools/analysis/bookkeeping.py
from __future__ import annotations

from typing import Dict, List, Any
import math

import numpy as np
import pandas as pd


def _validate_internal_df(df: pd.DataFrame) -> None:
    """
    Ensure the internal schema is present and minimally valid.
    Required columns: date, description, amount_gross, vat_rate, category.
    """
    required = ["date", "description", "amount_gross", "vat_rate", "category"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {', '.join(missing)}. "
            f"Got: {', '.join(df.columns)}"
        )

    # amount_gross must be numeric
    if not np.issubdtype(df["amount_gross"].dtype, np.number):
        raise ValueError("Column 'amount_gross' must be numeric (float).")

    # vat_rate can be float with NaN allowed
    if not np.issubdtype(df["vat_rate"].dtype, np.number):
        raise ValueError("Column 'vat_rate' must be numeric (float), NaN allowed.")

    # date is string 'YYYY-MM-DD'; we also try to parse to datetime for grouping
    if not np.issubdtype(df["date"].dtype, np.object_):
        # Accept pandas string dtype as well
        try:
            df["date"].astype(str)
        except Exception as e:
            raise ValueError(f"Column 'date' must be string-like: {e}")


def _compute_net_revenue(df: pd.DataFrame, gross_revenue: float) -> float:
    """
    If all vat_rate are NaN -> we don't know tax split yet; keep net=gross.
    Otherwise remove VAT component from each line:
      net = sum(amount_gross - amount_gross * r/(1+r)), where r is vat_rate.
    Negative amounts (returns) naturally reduce totals.
    """
    if df["vat_rate"].isna().all():
        return float(gross_revenue)

    # Compute VAT portion per line where rate is known; NaN treated as 0
    r = df["vat_rate"].fillna(0.0)
    vat_component = (df["amount_gross"] * (r / (1.0 + r))).fillna(0.0)
    net = float(gross_revenue - vat_component.sum())
    return net


def _group_key(series: pd.Series, mode: str) -> pd.Series:
    """
    Build a grouping key based on 'mode' using the 'date' or 'category'.
    - month: 'YYYY-MM'
    - quarter: 'YYYY-Qn'
    - category: category as-is
    """
    if mode == "category":
        return series.astype(str).fillna("uncategorized")

    # For month/quarter, parse date (string 'YYYY-MM-DD') to datetime
    # Errors='coerce' should not happen if loader validated, but we guard anyway.
    dt = pd.to_datetime(series, errors="coerce", format="%Y-%m-%d")

    if mode == "month":
        return dt.dt.strftime("%Y-%m").fillna("UNKNOWN")
    if mode == "quarter":
        # Quarter number 1..4
        q = ((dt.dt.month - 1) // 3 + 1).astype("Int64")
        year = dt.dt.year.astype("Int64")
        key = year.astype(str) + "-Q" + q.astype(str)
        key = key.fillna("UNKNOWN")
        return key

    # Fallback, though caller should not ask for other modes
    return pd.Series(["ALL"] * len(series))


def summarize(df: pd.DataFrame, groupby: str) -> Dict[str, Any]:
    """
    Produce a deterministic summary dict:
      {
        "n_transactions": int,
        "gross_revenue": float,
        "net_revenue": float,
        "returns": {"n": int, "sum": float},
        "by_group": [ {"key": str, "gross": float, "net": float, "n": int}, ... ]
      }

    - Negative amounts (returns/credits) are allowed and included in totals.
    - If all vat_rate are NaN -> net_revenue == gross_revenue (unknown VAT yet).
    - groupby ∈ {"month","quarter","category"} yields 'by_group'; otherwise empty.
    """
    _validate_internal_df(df)

    # Basic totals
    n_transactions = int(len(df))
    gross_revenue = float(df["amount_gross"].sum())

    # Net revenue (remove VAT portion if rates are known)
    net_revenue = _compute_net_revenue(df, gross_revenue)

    # Returns (negative amounts)
    negatives = df["amount_gross"] < 0
    returns_n = int(negatives.sum())
    returns_sum = float(df.loc[negatives, "amount_gross"].sum()) if returns_n else 0.0

    # Grouping
    by_group: List[Dict[str, Any]] = []
    allowed = {"month", "quarter", "category"}
    if isinstance(groupby, str) and groupby in allowed:
        if groupby in {"month", "quarter"}:
            key_series = _group_key(df["date"], groupby)
        else:
            key_series = _group_key(df["category"], "category")

        # Compute per-group totals deterministically
        tmp = pd.DataFrame(
            {
                "key": key_series,
                "amount_gross": df["amount_gross"].astype(float),
                "vat_rate": df["vat_rate"].astype(float),
            }
        )
        # For per-group net, reuse the same VAT removal logic
        # We'll aggregate by key: gross sum + vat_component sum
        r = tmp["vat_rate"].fillna(0.0)
        vat_component = (tmp["amount_gross"] * (r / (1.0 + r))).fillna(0.0)
        tmp = tmp.assign(vat_component=vat_component)

        grp = tmp.groupby("key", dropna=False, sort=True).agg(
            gross=("amount_gross", "sum"),
            vat=("vat_component", "sum"),
            n=("amount_gross", "count"),
        )
        # Build output rows; if all vat_rate NaN globally, net == gross for all groups
        if df["vat_rate"].isna().all():
            grp["net"] = grp["gross"]
        else:
            grp["net"] = grp["gross"] - grp["vat"]

        # Deterministic order by key (string compare)
        grp = grp.reset_index().sort_values("key", kind="mergesort")
        for _, row in grp.iterrows():
            by_group.append(
                {
                    "key": str(row["key"]),
                    "gross": float(row["gross"]),
                    "net": float(row["net"]),
                    "n": int(row["n"]),
                }
            )

    # Final summary dict
    summary = {
        "n_transactions": n_transactions,
        "gross_revenue": gross_revenue,
        "net_revenue": float(net_revenue),
        "returns": {"n": returns_n, "sum": returns_sum},
        "by_group": by_group,
    }
    return summary
