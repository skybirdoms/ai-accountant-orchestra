# Changelog

## Unreleased

### Added
- Added accountant agent (`agents/accountant_agent.py`) with natural-language BTW handling.
- Added accounting mode in CLI: `python main.py --ask "<query>"` triggers accountant agent when `--recipe` is not provided.
- Automatic BTW period parsing including RU/EN variants (e.g. "Q3 2025", "3 квартал 2025").
- Automatic brief generation in `workspace/drafts/brief_Qn-YYYY.md` (Gross / VAT / KOR).

### Changed
- `ui/cli.py`: extended `run_cli` to support accountant fallback mode when only `--ask` is provided.

### Breaking Changes
- None (added functionality does not break existing recipe-based workflows).


## [0.1.0] - 2025-11-06

### Added
- Initial skeleton: README with PyCharm quickstart and run configuration.
- `config.yaml` with `input_schema: kaggle_grocery_v1`, column mapping, and `description_format`.
- `rules/nl_vat_2025.yaml` placeholder VAT mapping (non-authoritative).
- `data/demo_transactions.csv` (includes a negative final_amount for demo).
- Validation stub in `tools/validation/schema.py` for `kaggle_grocery_v1`.
- `templates/reports/summary.j2.md` with negative totals section.
- `recipes/btw_return.yml` stub.
- `main.py` skeleton runner.
- `.env.example`, `.gitkeep` scaffolding.

### Breaking Changes
- None (public APIs are stubs; no runtime contracts promised yet).
