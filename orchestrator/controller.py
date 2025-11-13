"""Minimal recipe runner (Controller Builder GPT) — lazy placeholders + local imports priority.
- Load YAML recipe.
- Resolve ${...} placeholders lazily before each step:
    * supports ${steps.<name>.result} и ${steps.<name>.result_meta.*}
    * supports ${cfg.some.path}  (из config.yaml и overrides)
    * supports '| default(...)'  (например, ${steps.x.result_meta.row_count | default(0)})
    * ГЛОБАЛЬНЫЕ ПАРАМЕТРЫ: ${params.*} и топ-левел ${period} из CLI/--ask/--params
- Execute steps in order:
    * type: "tool" -> call Python function via importlib
    * type: "agent" -> NOOP with TODO log
- Cache step results by <name>.
- NDJSON step logs to workspace/logs/<timestamp>.ndjson.
- Fail-fast by default; allow policy.continue_on_error (root or step level).
- Error JSON on failure to workspace/errors/<timestamp>.json (traceback limit 5).
- Public API: run_recipe(recipe_path: str, overrides: dict|None) -> dict
"""
from __future__ import annotations

import json
import importlib
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any, Tuple
import sys

import yaml

try:
    import pandas as pd  # for DataFrame detection
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from orchestrator.memory import logs_path, errors_path, ts_iso_utc

# ----- гарантия приоритета локального проекта в импортах -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# -------------------------------------------------------------

# ----------------------------- Logging (NDJSON) -----------------------------

class NDJSONLogger:
    """Writes NDJSON lines with fixed key order:
       ts, level, event, step, status, duration_ms, message
    """
    def __init__(self, path: Path) -> None:
        self.path = path
        self.f = self.path.open("a", encoding="utf-8")

    def _line(self, level: str, event: str, step: str, status: str, duration_ms: float, message: str) -> str:
        rec = {
            "ts": ts_iso_utc(),
            "level": level,
            "event": event,
            "step": step,
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "message": message,
        }
        ordered = {k: rec[k] for k in ["ts", "level", "event", "step", "status", "duration_ms", "message"]}
        return json.dumps(ordered, ensure_ascii=False)

    def info(self, event: str, step: str, status: str, duration_ms: float, message: str = "") -> None:
        self.f.write(self._line("INFO", event, step, status, duration_ms, message) + "\n")
        self.f.flush()

    def error(self, event: str, step: str, duration_ms: float, message: str) -> None:
        self.f.write(self._line("ERROR", event, step, "FAILED", duration_ms, message) + "\n")
        self.f.flush()

    def close(self) -> None:
        try:
            self.f.close()
        except Exception:
            pass

# --------------------------- Config / placeholders --------------------------

_MISSING = object()

def _load_config() -> dict:
    cfg_path = Path("config.yaml")
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _merge_overrides(cfg: dict, overrides: dict | None) -> dict:
    if not overrides:
        return cfg
    # shallow merge — достаточно для минимального раннера
    return {**cfg, **overrides}

def _get_by_path(obj: Any, path: str) -> Any:
    """Безопасно обходит dot-path; возвращает _MISSING если путь не найден."""
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur

def _build_steps_context(cache_results: dict, cache_meta: dict) -> dict:
    """Формирует контекст для плейсхолдеров steps.*"""
    steps: dict[str, dict] = {}
    for name, res in cache_results.items():
        meta = cache_meta.get(name, {})
        steps[name] = {"result": res, "result_meta": meta}
    return {"steps": steps}

def _compute_result_meta(value: Any) -> dict:
    """Минимальные метаданные результата для плейсхолдеров .result_meta.*"""
    if pd is not None and isinstance(value, pd.DataFrame):
        return {
            "type": "DataFrame",
            "row_count": int(value.shape[0]),
            "col_count": int(value.shape[1]),
        }
    if isinstance(value, dict):
        return {"type": "dict", "keys": list(value.keys()), "len": len(value)}
    if isinstance(value, (str, Path)):
        return {"type": "path", "len": len(str(value))}
    return {"type": "other"}

def _coerce_default_literal(s: str) -> Any:
    """Пробует распарсить default(...) как JSON-литерал; если не вышло — вернёт строку."""
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        import json as _json
        return _json.loads(s)
    except Exception:
        lowered = s.lower()
        if lowered == "none":
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            if "." in s:
                return float(s)
            return int(s)
        except Exception:
            return s

def _resolve_placeholder_token(token: str, cfg: dict, steps_ctx: dict, gvars: dict) -> Tuple[Any, bool]:
    """
    Возвращает (value, exact) где exact=True если токен занимает ВСЮ строку (для возврата не-строковых объектов).
    Поддержка синтаксиса:
      ${steps.name.result_meta.row_count | default(0)}
      ${steps.name.result}
      ${cfg.some.path | default("x")}
      ${params.period} и топ-левел ${period}
    """
    raw = token.strip()
    inner = raw[2:-1].strip() if (raw.startswith("${") and raw.endswith("}")) else raw

    main_expr = inner
    default_val: Any = _MISSING
    if "|" in inner:
        left, right = inner.split("|", 1)
        main_expr = left.strip()
        right = right.strip()
        if right.lower().startswith("default"):
            lb = right.find("(")
            rb = right.rfind(")")
            if lb != -1 and rb != -1 and rb > lb:
                default_str = right[lb + 1 : rb]
                default_val = _coerce_default_literal(default_str)

    # приоритет: steps.* → cfg.* → globals (params/top-level) → cfg (as root)
    if main_expr.startswith("steps."):
        val = _get_by_path(steps_ctx, main_expr)
    elif main_expr.startswith("cfg."):
        val = _get_by_path({"cfg": cfg}, main_expr)
    else:
        # сначала globals (params и топ-левел ключи)
        val = _get_by_path(gvars, main_expr)
        if val is _MISSING:
            # затем попробуем в корне cfg (на случай, если overrides влит туда)
            val = _get_by_path(cfg, main_expr)

    if val is _MISSING:
        if default_val is not _MISSING:
            return (default_val, True)
        raise KeyError(f"Missing placeholder path: {main_expr}")

    return (val, True)

def _resolve_in_obj(node: Any, cfg: dict, steps_ctx: dict, gvars: dict) -> Any:
    """
    Рекурсивно разрешает плейсхолдеры в узле.
    Если строка состоит ровно из одного плейсхолдера — возвращаем исходный объект (не str).
    Если плейсхолдер внутри более длинной строки — подставляем str(value).
    """
    if isinstance(node, str):
        s = node
        out_parts = []
        i = 0
        any_token = False
        while True:
            start = s.find("${", i)
            if start == -1:
                out_parts.append(s[i:])
                break
            end = s.find("}", start + 2)
            if end == -1:
                out_parts.append(s[i:])
                break
            out_parts.append(s[i:start])
            token = s[start : end + 1]
            any_token = True
            val, exact = _resolve_placeholder_token(token, cfg, steps_ctx, gvars)
            if start == 0 and end == len(s) - 1:
                return val
            out_parts.append(str(val))
            i = end + 1
        if not any_token:
            return node
        return "".join(out_parts)

    if isinstance(node, list):
        return [_resolve_in_obj(x, cfg, steps_ctx, gvars) for x in node]
    if isinstance(node, dict):
        return {k: _resolve_in_obj(v, cfg, steps_ctx, gvars) for k, v in node.items()}
    return node

def resolve_placeholders_for_step(args_obj: Any, cfg: dict, steps_ctx: dict, gvars: dict) -> Any:
    """Разрешает плейсхолдеры в аргументах шага с учётом cfg, steps и глобальных переменных (params/топ-левел)."""
    return _resolve_in_obj(args_obj, cfg, steps_ctx, gvars)

# -------------------------------- Utilities ---------------------------------

def _import_callable(fn_path: str):
    mod_path, attr = fn_path.rsplit(".", 1)
    mod = importlib.import_module(mod_path)
    return getattr(mod, attr)

def _classify_result(value: Any) -> tuple[str, Any]:
    """Return (type, json-serializable value) for artifacts."""
    if pd is not None and isinstance(value, pd.DataFrame):
        return ("DataFrame", {"shape": [int(value.shape[0]), int(value.shape[1])]})
    if isinstance(value, dict):
        return ("dict", value)
    if isinstance(value, (str, Path)):
        return ("path", str(value))
    return ("other", repr(value))

def _should_continue(step_cfg: dict, policy: dict) -> bool:
    if "continue_on_error" in step_cfg:
        return bool(step_cfg["continue_on_error"])
    return bool(policy.get("continue_on_error", False))

# ------------------------------- Params merge --------------------------------

def _extract_params(overrides: dict | None) -> dict:
    """
    Приводит входные overrides от CLI к единому виду:
    - принимает {"period": "..."} ИЛИ {"params": {...}} ИЛИ их смесь
    - возвращает ровный dict параметров
    """
    params: dict = {}
    if not overrides:
        return params
    if isinstance(overrides, dict):
        # {params: {...}} поддержим как источник
        if isinstance(overrides.get("params"), dict):
            params.update(overrides["params"])
        # плюс положим top-level ключи (кроме 'params')
        for k, v in overrides.items():
            if k != "params":
                params[k] = v
    return params

# --------------------------------- Runner -----------------------------------

def run_recipe(recipe_path: str, overrides: dict | None = None) -> dict:
    """
    Execute a YAML recipe.
    Returns: {"status": "OK"/"FAILED"/"PARTIAL_SUCCESS", "artifacts": {...}}
    """
    log = NDJSONLogger(logs_path())
    artifacts: dict[str, dict] = {}
    cache_results: dict[str, Any] = {}
    cache_meta: dict[str, dict] = {}
    failures = 0

    try:
        with Path(recipe_path).open("r", encoding="utf-8") as f:
            recipe = yaml.safe_load(f) or {}

        policy = recipe.get("policy", {}) or {}
        steps = recipe.get("steps", []) or []

        # Config + параметры
        base_cfg = _load_config()
        params = _extract_params(overrides)
        # cfg остаётся как "config + overrides" (для обратной совместимости)
        cfg = _merge_overrides(base_cfg, overrides)

        # Глобальные переменные для плейсхолдеров (видимы как ${params.*} и как топ-левел ${key})
        gvars: dict[str, Any] = {"params": params}
        for k, v in params.items():
            if k not in gvars:
                gvars[k] = v

        for idx, step in enumerate(steps):
            step_id = str(step.get("id") or step.get("name") or f"step_{idx+1}")
            step_type = step.get("type", "tool")
            t0 = perf_counter()

            try:
                # ленивые плейсхолдеры — соберём контекст из уже выполненных шагов
                steps_ctx = _build_steps_context(cache_results, cache_meta)
                raw_args = step.get("args", {}) or {}
                args = resolve_placeholders_for_step(raw_args, cfg, steps_ctx, gvars)

                if step_type == "agent":
                    duration = (perf_counter() - t0) * 1000
                    cache_results[step_id] = {"todo": "Agent step not implemented yet."}
                    cache_meta[step_id] = {"type": "agent_todo"}
                    artifacts[step_id] = {"type": "agent_todo", "value": "NOOP"}
                    log.info(event="agent", step=step_id, status="OK", duration_ms=duration, message="TODO: implement agent")
                    continue

                fn_path: str = step["fn"]

                # спец-правило: для loader.load_dataframe добавим config_path по умолчанию
                if fn_path.endswith("tools.data_io.loader.load_dataframe") and "config_path" not in args:
                    args["config_path"] = "config.yaml"

                callable_fn = _import_callable(fn_path)
                result = callable_fn(**args)

                cache_results[step_id] = result
                cache_meta[step_id] = _compute_result_meta(result)

                r_type, r_val = _classify_result(result)
                artifacts[step_id] = {"type": r_type, "value": r_val}

                duration = (perf_counter() - t0) * 1000
                log.info(event="tool", step=step_id, status="OK", duration_ms=duration, message=f"fn={fn_path}")

            except Exception as e:
                failures += 1
                duration = (perf_counter() - t0) * 1000
                log.error(event="exception", step=step_id, duration_ms=duration, message=f"{type(e).__name__}: {e}")

                err_obj = {
                    "ts": ts_iso_utc(),
                    "recipe": recipe_path,
                    "step": step_id,
                    "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc(limit=5),
                }
                with errors_path().open("w", encoding="utf-8") as ef:
                    json.dump(err_obj, ef, ensure_ascii=False, indent=2)

                if not _should_continue(step, policy):
                    log.close()
                    return {"status": "FAILED", "artifacts": artifacts}

        log.close()
        if failures == 0:
            return {"status": "OK", "artifacts": artifacts}
        else:
            return {"status": "PARTIAL_SUCCESS", "artifacts": artifacts}

    except Exception as e:  # catastrophic error (before steps loop)
        log.error(event="fatal", step="controller", duration_ms=0.0, message=f"{type(e).__name__}: {e}")
        log.close()
        err_obj = {
            "ts": ts_iso_utc(),
            "recipe": recipe_path,
            "step": "controller",
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(limit=5),
        }
        with errors_path().open("w", encoding="utf-8") as ef:
            json.dump(err_obj, ef, ensure_ascii=False, indent=2)
        return {"status": "FAILED", "artifacts": {}}
