"""
Accountant agent: entrypoint for natural-language BTW queries.
"""

import json
import re
from pathlib import Path
from typing import Optional, Tuple

from orchestrator.controller import run_recipe


def _parse_period(query: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Try to extract quarter and year from a natural-language query.

    Supports patterns like:
    - "Q3 2025", "q1 2024", "2025Q4"
    - "3 квартал 2025", "за 1 кв 2024", "квартал 2 2025"

    Returns:
        (quarter, year) where each part can be None if it is not
        determined or is ambiguous (e.g., multiple different years
        mentioned in the query).
    """
    text = query.lower()

    # Collect all years like 2024, 2025, ...
    years = [int(y) for y in re.findall(r"(20\d{2})", text)]
    years = sorted(set(years))

    # Collect all quarters
    quarters: list[int] = []

    # Patterns: "q1", "q 2", "Q3 2025", "2025q4"
    for match in re.findall(r"\bq\s*([1-4])\b", text):
        quarters.append(int(match))
    for match in re.findall(r"\bq([1-4])\b", text):
        quarters.append(int(match))

    # Russian variants: "3 квартал", "3 кв"
    for match in re.findall(r"(\d)\s*(?:квартал|кв)\b", text):
        q = int(match)
        if 1 <= q <= 4:
            quarters.append(q)

    # Russian variants: "квартал 3", "кв 2"
    for match in re.findall(r"(?:квартал|кв)\s*(\d)", text):
        q = int(match)
        if 1 <= q <= 4:
            quarters.append(q)

    quarters = sorted(set(quarters))

    # If several distinct years/quarters are found, treat as ambiguous
    year: Optional[int] = years[0] if len(years) == 1 else None
    quarter: Optional[int] = quarters[0] if len(quarters) == 1 else None

    return quarter, year


def handle_query(query: str) -> dict:
    """
    Parse a natural-language BTW request, run the BTW recipe,
    and produce a short Markdown brief with totals.

    Returns:
        {
            "status": "OK" | "FAILED",
            "period": "Qn-YYYY" | None,
            "brief_path": "workspace/drafts/brief_Qn-YYYY.md" | None,
            "artifacts": {...}  # controller artifacts or {}
        }
    """
    try:
        # 1. Parse period from the initial query
        quarter, year = _parse_period(query)

        # If the period is incomplete/ambiguous, ask once for clarification
        if quarter is None or year is None:
            answer = input(
                "Я не смог однозначно понять период BTW. "
                "Укажи квартал и год, например: 'Q3 2025' или '3 квартал 2025': "
            )
            quarter, year = _parse_period(answer)

        # If still no clear period — give up gracefully
        if quarter is None or year is None:
            print("Не удалось однозначно определить период BTW.")
            return {
                "status": "FAILED",
                "period": None,
                "brief_path": None,
                "artifacts": {},
            }

        period_str = f"Q{quarter}-{year}"
        print(f"[accountant] Parsed period: {period_str}")

        # 2. Run BTW recipe via controller
        overrides = {
            "params": {"period": period_str},
            "period": period_str,
        }
        ctrl_result = run_recipe("recipes/btw_return.yml", overrides=overrides)

        status = ctrl_result.get("status", "FAILED")
        artifacts = ctrl_result.get("artifacts", {})

        if status != "OK":
            print(f"Контроллер вернул статус {status}. См. логи в workspace/logs/.")
            return {
                "status": "FAILED",
                "period": period_str,
                "brief_path": None,
                "artifacts": artifacts,
            }

        # 3. Load latest summary JSON produced by the pipeline
        summary_path = Path("workspace") / "summary_latest.json"
        if not summary_path.exists():
            print(f"Не найден файл сводки: {summary_path}")
            return {
                "status": "FAILED",
                "period": period_str,
                "brief_path": None,
                "artifacts": artifacts,
            }

        with summary_path.open("r", encoding="utf-8") as f:
            summary = json.load(f)

        # Extract totals
        gross = summary.get("gross_revenue")
        gross_val: Optional[float]
        if isinstance(gross, (int, float)):
            gross_val = float(gross)
        else:
            gross_val = None

        # VAT total: sum tax_amount over groups as a robust fallback
        vat_total = 0.0
        for group in summary.get("by_group", []):
            ta = group.get("tax_amount")
            if isinstance(ta, (int, float)):
                vat_total += float(ta)

        kor_applied = bool(summary.get("kor_applied"))

        # 4. Prepare drafts directory and brief path
        drafts_dir = Path("workspace") / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        brief_path = drafts_dir / f"brief_{period_str}.md"

        # 5. Render three-line Markdown brief
        if gross_val is not None:
            gross_line = f"Gross: {gross_val:.2f} EUR"
        else:
            gross_line = f"Gross: {gross} EUR"

        vat_line = f"VAT: {vat_total:.2f} EUR"
        kor_line = f"KOR: {'YES' if kor_applied else 'NO'}"

        lines = [gross_line, vat_line, kor_line]

        # Write brief to file
        with brief_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # Also print lines to console for convenience
        for line in lines:
            print(line)

        return {
            "status": "OK",
            "period": period_str,
            "brief_path": str(brief_path),
            "artifacts": artifacts,
        }

    except Exception as exc:
        print(f"Ошибка при обработке запроса бухгалтера: {exc}")
        return {
            "status": "FAILED",
            "period": None,
            "brief_path": None,
            "artifacts": {},
        }
