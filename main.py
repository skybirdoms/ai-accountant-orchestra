# main.py
"""
ai-accountant-orchestra entry point

Usage examples:
  python main.py --recipe recipes/btw_return.yml
  python main.py --recipe recipes/btw_return.yml --params period=Q3-2025
  python main.py --ask "btw за Q3 2025"
"""

import sys
import json
from pathlib import Path

try:
    from ui.cli import main as cli_main
except Exception as e:
    cli_main = None
    _cli_import_error = e
else:
    _cli_import_error = None


def fallback_main():
    import argparse
    parser = argparse.ArgumentParser(description="ai-accountant-orchestra skeleton runner (fallback)")
    parser.add_argument("--recipe", required=True, help="Path to a YAML recipe (stub)")
    args = parser.parse_args()

    recipe_path = Path(args.recipe)
    if not recipe_path.exists():
        print(json.dumps({"status": "FAILED", "error": f"Recipe not found: {recipe_path.as_posix()}"}))
        sys.exit(1)

    result = {
        "status": "OK",
        "message": "Skeleton runner (fallback): no business logic executed.",
        "recipe": recipe_path.as_posix()
    }
    print(json.dumps(result))
    sys.exit(0)


def main():
    if cli_main is not None:
        return cli_main()
    else:
        print(f"[WARN] CLI not available: {_cli_import_error}")
        return fallback_main()


if __name__ == "__main__":
    sys.exit(main())
