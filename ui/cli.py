# ui/cli.py
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

# Контроллер
try:
    from orchestrator.controller import run_recipe  # type: ignore
except Exception as e:
    run_recipe = None
    _import_error = e
else:
    _import_error = None

console = Console()


def parse_kv_params(pairs: List[str]) -> Dict[str, str]:
    """Парсит список key=value в dict. Пробелы вокруг = не допускаются."""
    out: Dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Ожидалось key=value, а получено: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Пустой ключ в паре: {item!r}")
        out[key] = value
    return out


_QRUS = r"(?:кв(?:артал)?|Q)\s*([1-4])"
_YEAR = r"(\d{4})"


def parse_ask(text: str) -> Dict[str, str]:
    """
    '--ask "btw за Q3 2025"'     -> {'period': 'Q3-2025'}
    '--ask "BTW за 2 квартал 25"' -> {'period': 'Q2-2025'} (если указан полный год)
    """
    t = text.strip()
    m = re.search(rf"{_QRUS}\D+{_YEAR}", t, flags=re.IGNORECASE)
    if not m:
        m = re.search(rf"{_YEAR}\D+{_QRUS}", t, flags=re.IGNORECASE)
        if not m:
            return {}
        year, q = m.group(1), m.group(2)
    else:
        q, year = m.group(1), m.group(2)

    q = q.strip()
    year = year.strip()
    if q not in {"1", "2", "3", "4"}:
        return {}
    return {"period": f"Q{q}-{year}"}


def latest_log_path(log_dir: Path) -> Optional[Path]:
    if not log_dir.exists():
        return None
    files = sorted(log_dir.glob("*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def pretty_print_result(result: Dict, workdir: Path) -> None:
    status = result.get("status", "UNKNOWN")
    artifacts = result.get("artifacts", {})

    console.print(Panel.fit(f"[bold]STATUS:[/bold] {status}"))

    table = Table(title="Artifacts", show_lines=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    def _fmt(val) -> str:
        if isinstance(val, (str, Path)):
            return str(val)
        try:
            return json.dumps(val, ensure_ascii=False, indent=2)
        except Exception:
            return repr(val)

    if isinstance(artifacts, dict) and artifacts:
        for k, v in artifacts.items():
            table.add_row(str(k), _fmt(v))
        console.print(table)
    else:
        console.print("[dim]Артефактов не обнаружено.[/dim]")

    log_dir = workdir / "workspace" / "logs"
    last_log = latest_log_path(log_dir)
    if last_log:
        console.print(f"📜 Лог: [underline]{last_log}[/underline]")
    else:
        console.print("📜 Логов пока нет (ожидалась папка workspace/logs).")


def run_cli(recipe: Optional[str], ask: Optional[str], params_kv: List[str]) -> int:
    if _import_error is not None:
        console.print(f"[red]Не удалось импортировать orchestrator.controller.run_recipe[/red]\n{_import_error}")
        return 2

    workdir = Path.cwd()

    params: Dict[str, str] = {}
    if params_kv:
        try:
            params.update(parse_kv_params(params_kv))
        except ValueError as e:
            console.print(f"[red]Ошибка парсинга --params:[/red] {e}")
            return 2

    if ask:
        parsed = parse_ask(ask)
        if parsed:
            params.update(parsed)
            console.print(f"[dim]Распознанные параметры из --ask:[/dim] {parsed}")
        else:
            console.print("[yellow]Предупреждение:[/yellow] не удалось извлечь период из --ask. Продолжаю без него.")

    # Новый режим: если есть --ask, но нет --recipe → вызываем бухгалтера
    if not recipe:
        if ask:
            try:
                from agents.accountant_agent import handle_query
            except ImportError as e:
                console.print("[red]Не удалось импортировать agents.accountant_agent.handle_query[/red]")
                console.print(str(e))
                return 2

            console.print(Panel.fit("▶ Режим бухгалтера: BTW по свободному запросу"))

            result = handle_query(ask)

            if isinstance(result, dict):
                console.print("[dim]Результат бухгалтера:[/dim]")
                console.print(JSON.from_data(result))

                status = result.get("status")
                return 0 if status == "OK" else 1

            console.print("[red]Агент бухгалтера вернул неожиданный результат.[/red]")
            return 1

        console.print("[red]Нужен --recipe <path>[/red]. Пример: --recipe recipes/btw_return.yml --ask \"btw за Q3 2025\"")
        return 2

    # Обычный режим: запускаем явный рецепт
    recipe_path = str(recipe)

    console.print(Panel.fit(f"▶ Запуск рецепта: [bold]{recipe_path}[/bold]"))
    if params:
        console.print("Параметры:", JSON.from_data(params))

    # КЛЮЧЕВАЯ ЧАСТЬ: пробрасываем overrides для ${params.*} и коротких ${period}
    overrides = {"params": params, **params}

    try:
        result = run_recipe(recipe_path, overrides=overrides)  # type: ignore
    except TypeError as e:
        # Фолбэк, если контроллер старый и не знает про overrides
        if "unexpected keyword argument 'overrides'" in str(e):
            console.print("[yellow]Контроллер не принимает 'overrides'; пробую без него.[/yellow]")
            result = run_recipe(recipe_path)  # type: ignore
        else:
            console.print(f"[red]Ошибка исполнения рецепта:[/red] {e}")
            return 1
    except Exception as e:
        console.print(f"[red]Ошибка исполнения рецепта:[/red] {e}")
        return 1

    if not isinstance(result, dict):
        console.print("[red]Контроллер вернул не-JSON результат. Ожидался dict.[/red]")
        return 1

    pretty_print_result(result, workdir)
    return 0



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-accountant-orchestra",
        description="CLI для запуска YAML-рецептов и режима --ask."
    )
    p.add_argument("--recipe", type=str, help="Путь к рецепту .yml")
    p.add_argument("--ask", type=str, help="Свободный запрос. Пример: \"btw за Q3 2025\"")
    p.add_argument(
        "--params",
        nargs="*",
        default=[],
        help="Доп. параметры в формате key=value (можно несколько).",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_cli(args.recipe, args.ask, args.params)


if __name__ == "__main__":
    raise SystemExit(main())
