# tools/data_io/loader.py
from __future__ import annotations

import io
import json
import math
import os
from typing import Dict, Any, Iterable

import numpy as np
import pandas as pd
import yaml
from datetime import datetime
from string import Formatter


def _read_config(config_path: str) -> Dict[str, Any]:
    """Load YAML config (UTF-8). Raise clear error if invalid/missing."""
    if not os.path.exists(config_path):
        raise ValueError(f"Config file not found: {config_path}")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        raise ValueError(f"Failed to read YAML config '{config_path}': {e}")
    return cfg


def _required_placeholders(fmt: str) -> Iterable[str]:
    """Extract field names used inside a str.format template."""
    for literal_text, field_name, format_spec, conversion in Formatter().parse(fmt):
        if field_name is not None and field_name != "":
            # Support dotted names like "a.b" is not expected here; keep simple.
            yield field_name


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Coerce series to numeric floats, preserving NaN; strip strings first."""
    if series.dtype == object:
        series = series.astype(str).str.strip()
    return pd.to_numeric(series, errors="coerce")


def _normalize_str(series: pd.Series) -> pd.Series:
    """Normalize to string, strip spaces, treat NaN as empty string."""
    return series.astype(str).str.strip().fillna("")


def _read_table_by_extension(path: str) -> pd.DataFrame:
    """Read CSV/XLSX/JSON/NDJSON (jsonl) by extension."""
    if not os.path.exists(path):
        raise ValueError(f"Input file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in [".csv"]:
            return pd.read_csv(path)
        if ext in [".xlsx", ".xls"]:
            return pd.read_excel(path)
        if ext in [".ndjson", ".jsonl"]:
            return pd.read_json(path, lines=True)
        if ext in [".json"]:
            # Try to detect JSON array vs. JSON Lines by peeking first byte(s)
            with open(path, "r", encoding="utf-8") as f:
                head = f.read(2)
            if head.strip().startswith("["):
                return pd.read_json(path)
            return pd.read_json(path, lines=True)
    except Exception as e:
        raise ValueError(f"Failed to read data from '{path}': {e}")

    raise ValueError(
        f"Unsupported file extension '{ext}'. Use CSV/XLSX/JSON/NDJSON."
    )


def _validate_columns(df: pd.DataFrame, required: Iterable[str], ctx: str) -> None:
    """Ensure required source columns exist; raise ValueError listing missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s) for {ctx}: {', '.join(missing)}. "
            f"Available: {', '.join(df.columns)}"
        )


def _parse_date_yyyymmdd(series: pd.Series) -> pd.Series:
    """Parse to ISO date string 'YYYY-MM-DD' (UTC-naive)."""
    # Accept a variety of inputs; errors='coerce' -> NaT for bad rows.
    s = pd.to_datetime(series, errors="coerce", utc=False)
    if s.isna().any():
        bad = series[s.isna()]
        # Show only a few examples to keep error readable.
        examples = ", ".join(map(str, bad.head(3).tolist()))
        raise ValueError(
            f"Failed to parse some dates. Examples of invalid values: {examples}"
        )
    return s.dt.strftime("%Y-%m-%d")


def load_dataframe(path: str, *, config_path: str = "config.yaml") -> "pd.DataFrame":
    """
    Load external data and build an internal DataFrame with REQUIRED columns:
      - date (ISO8601 'YYYY-MM-DD')
      - description (str)
      - amount_gross (float)
      - vat_rate (float | NaN)
      - category (str)

    Behavior is config-driven. It expects in YAML:
      input_schema: e.g., "kaggle_grocery_v1"
      column_mapping:
        <schema_name>:
          date: transaction_date
          description_candidates: [product_name, store_name]   # optional, for validation only
          amount:
            preferred: final_amount
            fallback_expr: total_amount - discount_amount
          category: aisle
      description_format: "{product_name}" or "{store_name} - {product_name}"

    For schema 'kaggle_grocery_v1' we apply the specified rules and allow
    negative amounts (returns/credits) to pass through.

    Raises ValueError with clear messages for missing columns or invalid types.
    """
    cfg = _read_config(config_path)

    schema = cfg.get("input_schema")
    if not schema:
        raise ValueError("Config is missing 'input_schema'.")

    mappings_all = (cfg.get("column_mapping") or {})
    mapping = (mappings_all.get(schema) or {})
    if not mapping:
        raise ValueError(
            f"Config missing 'column_mapping' for schema '{schema}'."
        )

    desc_fmt = cfg.get("description_format")
    if not isinstance(desc_fmt, str) or not desc_fmt:
        raise ValueError("Config must include non-empty 'description_format' string.")

    # Read source table
    df_src = _read_table_by_extension(path)
    # Normalize column names (strip only)
    df_src.columns = df_src.columns.astype(str).str.strip()

    # --- Validate mandatory source columns depending on schema rules ---
    # date
    src_date_col = mapping.get("date", "transaction_date")

    # description placeholders must exist in df_src
    placeholders = list(_required_placeholders(desc_fmt))
    # If config optionally lists candidates to help validation, include them
    extra_desc_candidates = mapping.get("description_candidates") or []
    description_required_cols = set(placeholders)  # placeholders must be columns

    # amount: prefer preferred; else fallback expression requires two columns
    amount_cfg = mapping.get("amount", {})
    preferred_amount_col = amount_cfg.get("preferred", "final_amount")
    fallback_expr = amount_cfg.get("fallback_expr", "total_amount - discount_amount")
    # Parse fallback expression "A - B" (very simple)
    fb_left, fb_right = None, None
    if fallback_expr and "-" in fallback_expr:
        parts = [p.strip() for p in fallback_expr.split("-", 1)]
        if len(parts) == 2:
            fb_left, fb_right = parts[0], parts[1]

    # category
    src_category_col = mapping.get("category", "aisle")

    # Build required column list for validation
    required_cols = {src_date_col, src_category_col}
    required_cols.update(description_required_cols)
    # For amount: either preferred exists OR fallback pair exist; require both sets for clear message.
    # We'll validate presence and then choose at runtime.
    if preferred_amount_col:
        required_cols.add(preferred_amount_col)
    if fb_left and fb_right:
        required_cols.update([fb_left, fb_right])

    _validate_columns(df_src, required_cols, ctx=f"schema '{schema}'")

    # --- Build internal columns ---
    # date
    date_series = _parse_date_yyyymmdd(df_src[src_date_col])

    # description via template
    # Ensure placeholders exist (already validated)
    def _fmt_row(row: pd.Series) -> str:
        # Use dict(row) to support {column_name} placeholders
        try:
            return str(desc_fmt.format(**row.to_dict()))
        except KeyError as e:
            # Should not happen due to validation; still guard.
            raise ValueError(
                f"Description template refers to missing field: {e}"
            )

    description_series = df_src.apply(_fmt_row, axis=1).astype(str).str.strip()

    # amount_gross: preferred else fallback(total_amount - discount_amount)
    amount_series = None
    if preferred_amount_col in df_src.columns and not df_src[preferred_amount_col].isna().all():
        amount_series = _coerce_numeric(df_src[preferred_amount_col])
    else:
        if fb_left and fb_right and fb_left in df_src.columns and fb_right in df_src.columns:
            amount_series = _coerce_numeric(df_src[fb_left]) - _coerce_numeric(df_src[fb_right])
        else:
            raise ValueError(
                "Cannot resolve amount_gross: neither preferred amount is present nor valid fallback expression."
            )

    if amount_series.isna().any():
        # We allow NaN but warn loudly via exception to keep pipeline deterministic.
        bad_n = int(amount_series.isna().sum())
        raise ValueError(
            f"{bad_n} row(s) have non-numeric amount values after coercion; please fix the source data."
        )

    # category with fallback to 'uncategorized'
    category_series = (
        _normalize_str(df_src[src_category_col])
        if src_category_col in df_src.columns
        else pd.Series(["uncategorized"] * len(df_src))
    )
    category_series = category_series.replace({"": "uncategorized"})

    # vat_rate is not known at this stage -> NaN
    vat_rate_series = pd.Series([np.nan] * len(df_src), dtype="float64")

    # Final internal DataFrame in required order
    internal = pd.DataFrame(
        {
            "date": date_series,
            "description": description_series,
            "amount_gross": amount_series.astype(float),
            "vat_rate": vat_rate_series,
            "category": category_series.astype(str),
        }
    )

    # Final sanity checks
    if internal["date"].isna().any():
        raise ValueError("Internal 'date' contains NaN after parsing.")
    if internal["description"].isna().any():
        raise ValueError("Internal 'description' contains NaN after formatting.")
    if internal["amount_gross"].isna().any():
        raise ValueError("Internal 'amount_gross' contains NaN after computation.")
    if internal["category"].isna().any():
        raise ValueError("Internal 'category' contains NaN after mapping.")

    # Negative amounts are allowed (returns/credits)
    # Nothing to do here — just document:
    # - Do not clamp; downstream steps will include them in totals.

    return internal
