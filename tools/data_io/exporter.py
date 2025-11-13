# tools/data_io/exporter.py
from __future__ import annotations

import json
import ast
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import date

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _unwrap(obj: Any) -> Any:
    """{"type": "...", "value": ...} → value"""
    if isinstance(obj, dict) and "type" in obj and "value" in obj:
        return obj["value"]
    return obj


def _extract_balanced_dict_str(s: str) -> Optional[str]:
    """
    Извлекает первую сбалансированную подстроку {...} из строки.
    Идём от первой '{' и считаем скобки до нулевой глубины.
    """
    if not isinstance(s, str):
        return None
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _coerce_mapping(obj: Any) -> Dict[str, Any]:
    """
    Приводит obj к dict:
      - dict → dict
      - JSON string → dict
      - Python-literal string → dict
      - «грязная» строка → берём балансную {...} и парсим
      - иначе → {}
    """
    if isinstance(obj, dict):
        return obj

    if isinstance(obj, str):
        # 1) Чистый JSON
        try:
            loaded = json.loads(obj)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass

        # 2) Безопасный питон-литерал
        try:
            loaded = ast.literal_eval(obj)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass

        # 3) Грязная строка: вытащим балансный блок {...}
        core = _extract_balanced_dict_str(obj)
        if core:
            # Попытка JSON (заменим одиночные кавычки на двойные)
            try:
                loaded = json.loads(core.replace("'", '"'))
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass
            # Попытка literal_eval
            try:
                loaded = ast.literal_eval(core)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass

    return {}


def save_summary(summary: dict,
                 md_path: str = "workspace/summary_latest.md",
                 json_path: str = "workspace/summary_latest.json",
                 meta: dict | None = None,
                 template_path: str = "templates/reports/summary.j2.md") -> dict:
    """
    Сохраняет JSON и рендерит Markdown через Jinja2-шаблон.
    summary — словарь из summarize(); meta может содержать:
      - period (или params.period)
      - kor_applied: bool
      - vat_breakdown: {"low": float, "high": float}
      - today/run_date/generation_date
    """
    # Нормализуем входы
    summary = _coerce_mapping(_unwrap(summary)) if summary is not None else {}
    meta = _coerce_mapping(meta) if meta else {}

    # Гарантируем, что папки существуют
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)

    # 1) JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 2) Markdown через шаблон (абсолютный путь к шаблону, без chdir)
    project_root = Path(__file__).resolve().parents[2]
    tpl_file = (project_root / template_path).resolve()

    if tpl_file.exists():
        env = Environment(
            loader=FileSystemLoader(str(tpl_file.parent)),
            autoescape=select_autoescape(disabled_extensions=("md",))
        )
        tpl = env.get_template(tpl_file.name)

        # --- АВТО-РАСЧЁТ VAT BREAKDOWN, если не передан в meta ---
        # Маппинг категорий → ставка BTW (простая демо-карта под текущие демо-данные)
        _rate_by_category = {
            "Produce": 0.09,
            "Bakery": 0.09,
            "Dairy": 0.09,
            "Alcohol": 0.21,
            "Household": 0.21,
        }

        # Подсчёт налога, «заложенного» в брутто: tax = gross * r/(1+r)
        low_tax = 0.0
        high_tax = 0.0
        for g in summary.get("by_group", []):
            cat = (g.get("key") or "").strip()
            gross = float(g.get("gross", 0.0) or 0.0)
            r = _rate_by_category.get(cat)
            if r is None or gross == 0.0:
                continue
            tax_in_gross = gross * (r / (1.0 + r))
            if abs(r - 0.09) < 1e-12:
                low_tax += tax_in_gross
            elif abs(r - 0.21) < 1e-12:
                high_tax += tax_in_gross

        meta_vbd = meta.get("vat_breakdown")
        if not isinstance(meta_vbd, dict) or (
            float(meta_vbd.get("low", 0.0) or 0.0) == 0.0
            and float(meta_vbd.get("high", 0.0) or 0.0) == 0.0
        ):
            vat_breakdown = {"low": round(low_tax, 2), "high": round(high_tax, 2)}
        else:
            vat_breakdown = {
                "low": float(meta_vbd.get("low", 0.0) or 0.0),
                "high": float(meta_vbd.get("high", 0.0) or 0.0),
            }
        # -----------------------------------------------------------

        period = meta.get("period") or (meta.get("params") or {}).get("period") or "N/A"
        ctx = {
            "summary": summary,
            "period": period,
            "params": meta.get("params") or {},
            "kor_applied": bool(meta.get("kor_applied", False)),
            "vat_breakdown": vat_breakdown,  # используем рассчитанное/переданное
            "today": meta.get("today") or meta.get("run_date") or meta.get("generation_date") or date.today().isoformat(),
        }

        md = tpl.render(**ctx)
    else:
        # Фоллбэк: «draft», если шаблон не найден
        lines = [
            "# BTW Summary (draft)",
            f"- Transactions: {summary.get('n_transactions', 0)}",
            f"- Gross: {summary.get('gross_revenue', 0):.2f}",
            f"- Net: {summary.get('net_revenue', 0):.2f}",
            f"- KOR applied: {bool(meta.get('kor_applied', False))}",
            f"- VAT breakdown: low={(meta.get('vat_breakdown') or {}).get('low', 0.0):.2f}, high={(meta.get('vat_breakdown') or {}).get('high', 0.0):.2f}",
            "",
            "## By category",
        ]
        for g in summary.get("by_group", []):
            lines.append(f"- {g.get('key')}: gross={g.get('gross',0)}, net={g.get('net',0)}, n={g.get('n',0)}")
        md = "\n".join(lines)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    return {"json_path": json_path, "md_path": md_path}
