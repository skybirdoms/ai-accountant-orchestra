\# Developer Overview



This document explains the internal architecture of the AI-Accountant-Orchestra project  

and describes how its components work together as a deterministic accounting pipeline.



The goal is to demonstrate the system design, extendability, and engineering decisions  

behind the project.



---



\## 1. System Philosophy



AI-Accountant-Orchestra follows three principles:



1\. \*\*Deterministic execution\*\* — every run produces reproducible results.

2\. \*\*Recipe-driven orchestration\*\* — business logic lives in YAML, not code.

3\. \*\*Modularity\*\* — loaders, validators, analyzers, and exporters can be replaced independently.



This makes the system easy to extend for real businesses and compatible with future AI agents.



---



\## 2. High-Level Flow



1\. A YAML recipe defines the workflow.

2\. `main.py` passes the recipe to the orchestrator.

3\. The orchestrator resolves steps and loads required agents.

4\. Tools (loader, validation, tax, summarizer) process the data.

5\. Artifacts and logs are created in the `workspace/`.



This structure allows new computation steps to be added without rewriting the core.



---



\## 3. Core Components



\### \*\*orchestrator/\*\*

Contains the main controller that executes YAML recipes step-by-step:

\- loads steps

\- passes parameters

\- logs deterministic events

\- routes data between tools and agents



\### \*\*recipes/\*\*

Business logic as YAML:

\- BTW return

\- test loaders

\- future LLM-enabled agents



This lets users build pipelines without touching Python code.



\### \*\*tools/\*\*

Low-level, predictable utilities:

\- `data\_io` — CSV loader, exporter

\- `validation` — schema checks

\- `analysis` — VAT/KOR calculation, grouping

\- `taxonomy` — rules for categories and rates



These modules are pure and testable.



\### \*\*agents/\*\*

Specialized processors that orchestrator can call dynamically.

Agents allow the system to scale into:

\- AI assistants  

\- multi-step bookkeeping flows  

\- business-specific automations  



\### \*\*workspace/\*\*

All outputs:

\- `logs/\*.ndjson`

\- `reports/\*.json`

\- cached summaries



This keeps runs fully observable.



---



\## 4. Determinism \& Logging



Every run produces:



\- timestamped NDJSON logs  

\- structured summaries  

\- reproducible JSON artifacts  



This mirrors the logging discipline used in fintech and auditing.



---



\## 5. Extensibility



Users can add:



\- new recipes (`recipes/`)

\- new VAT rules (`rules/`)

\- new analysis modules (`tools/analysis/`)

\- new agents (`agents/`)

\- LLM-supported steps (future `agents/ai/`)



The system becomes a foundation for:

\- automated BTW reporting  

\- SME bookkeeping pipelines  

\- data validation systems  

\- ML-driven anomaly detection  



---



\## 6. Future AI Integration



The architecture is purposely designed for a plug-in LLM layer:



\- each step becomes an agent  

\- an LLM-agent can generate or modify recipes  

\- human-in-the-loop validation stays via logs  



This turns the project into a real AI bookkeeping assistant.



---



