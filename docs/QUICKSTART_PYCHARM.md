\# PyCharm Quickstart



This guide explains how to run the AI-Accountant-Orchestra project inside PyCharm with a clean, reproducible workflow.



---



\## 1. Create a Virtual Environment



```bash

python -m venv .venv

.venv\\Scripts\\activate     # Windows

Dependencies (minimum for running recipes):



bash

Копировать код

pip install pandas jinja2

If you plan to run tests or development tools:



bash

Копировать код

pip install -r requirements.txt

2\. Configure PyCharm Run Configuration

Run → Edit Configurations → Add New → Python



Set:



Script path: main.py



Parameters:



bash

Копировать код

--recipe recipes/btw\_return.yml --ask "btw за Q3 2025"

Working directory:

ai-accountant-orchestra/



Interpreter:

.venv created earlier



This allows PyCharm to correctly resolve imports such as:



python

Копировать код

from tools.validation.schema import validate\_schema

3\. Run the Project

Click ▶ Run or press Shift+F10.



Expected minimal output for the skeleton version:



json

Копировать код

{

&nbsp; "status": "OK",

&nbsp; "message": "Skeleton runner: no business logic executed.",

&nbsp; "recipe": "recipes/btw\_return.yml"

}

4\. Notes for Development

The tools/ package is fully importable because the working directory is set to project root.



NDJSON logs and generated reports appear inside workspace/.



Recipes are YAML files inside recipes/ and can be extended or modified.



If you work with datasets, ensure the paths in config.yaml are aligned with your environment.



5\. Tips

Use PyCharm File Watchers if you want auto-run on edits.



For debugging, set breakpoints inside:



orchestrator/controller.py



agents/



tools/analysis/



If you enable LLM agents in the future, place your keys inside .env (never commit it).





