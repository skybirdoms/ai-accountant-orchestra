# AI-Accountant-Orchestra  
![Tests](https://github.com/<user>/<repo>/actions/workflows/ci.yml/badge.svg)  
![Python](https://img.shields.io/badge/Python-3.11-blue)  
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Short Description

AI-Accountant-Orchestra is a modular, YAML-driven accounting automation framework.  
It loads transactions, validates data, computes VAT (BTW), produces summaries,  
and generates artifacts — all orchestrated using a fully deterministic recipe system.  
The project is suitable for small and medium businesses, especially in the Netherlands,  
where VAT and BTW returns play a central role in financial workflows.

By adjusting dataset paths (and optionally adding API keys in the future),  
the framework can be connected to real financial operations.

---

## Example Output

▶ Loading data...
Rows loaded: 10

▶ VAT summary:
Gross: 13.07
Net: 13.07
Groups:

Dairy: -1.85

Produce: 14.92

▶ Artifacts saved in workspace/reports/



---

## Features / What the System Can Do

- Deterministic execution of YAML accounting recipes  
- Load and normalize transactional data (CSV or custom sources)  
- Compute VAT with Dutch low/high rates  
- Basic support for KOR (Kleineondernemersregeling)  
- Produce BTW-ready summaries for business reporting  
- Data validation and schema checks  
- NDJSON logging and reproducible run outputs  
- Artifact generation inside `workspace/`  
- Clear modular architecture designed for further AI agent integration  
- Full test suite ready for CI

---

## Installation

```bash
git clone <repo>
cd ai-accountant-orchestra
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
Run Examples

python main.py --recipe recipes/test_load.yml
python main.py --recipe recipes/btw_return.yml --params period=Q3-2025
python main.py --recipe recipes/btw_return.yml --ask "btw за Q3 2025"
Project Structure

ai-accountant-orchestra/
│
├── main.py
├── README.md
├── CHANGELOG.md
├── LICENSE
├── config.yaml
├── .env.example
├── sample_data.csv
│
├── agents/
├── orchestrator/
├── templates/
├── tools/
├── rules/
├── recipes/
│
├── workspace/
│   ├── logs/
│   └── reports/
│
├── tests/
├── data/
└── docs/
    ├── QUICKSTART_PYCHARM.md
    └── NL_VAT_KOR_GUIDE.md
Technologies Used
Python 3.11

Pandas — data processing

PyYAML — recipe and config parsing

Rich — CLI formatting

pytest — testing

NDJSON — reproducible logs

GitHub Actions — automated CI

Tests
Run all tests:

pytest -q
Additional Documentation
PyCharm Quickstart:
docs/QUICKSTART_PYCHARM.md

Dutch VAT & KOR Guide:
docs/NL_VAT_KOR_GUIDE.md

License
This project is licensed under the MIT License.
See the LICENSE file for details.

Changelog
See full release notes here:
CHANGELOG.md




