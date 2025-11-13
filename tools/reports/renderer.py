def render_report(**kwargs):
    result = {"ok": True, "received_keys": sorted(kwargs.keys())}
    print("[reports.renderer] received keys:", result["received_keys"])
    return result

def render_markdown(df=None, meta=None, period=None, **kwargs):
    row_count = len(df) if df is not None and hasattr(df, "__len__") else 0
    # 👇 диагностика: увидим значение period и доступные ключи
    print(f"[diag] period={period!r}; kwargs={sorted(kwargs.keys())}")
    lines = [
        "# BTW Report (draft)",
        f"- Period: {period or 'N/A'}",
        f"- Rows: {row_count}",
        f"- Meta keys: {sorted(list(meta.keys())) if isinstance(meta, dict) else []}",
    ]
    md = "\n".join(lines)
    print("[reports.renderer] markdown produced")
    return {"ok": True, "markdown": md}

