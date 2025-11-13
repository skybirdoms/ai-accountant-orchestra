# Architecture Diagram

Below is the high-level architecture of the AI-Accountant-Orchestra project.

---

## Mermaid Diagram

```mermaid
flowchart TD

    A[Input CSV / Data Source] --> B[tools.data_io.loader]
    B --> C[tools.validation.schema]
    C --> D[tools.analysis.tax]
    D --> E[tools.analysis.bookkeeping]

    E --> F[orchestrator.controller]
    F --> G[agents/*]

    G --> H[workspace/reports]
    F --> I[workspace/logs]

    subgraph Recipes
        R1[recipes/btw_return.yml]
        R2[recipes/test_load.yml]
    end

    R1 --> F
    R2 --> F
Description
1. Data Layer
Raw transactions are loaded via tools.data_io.loader, using paths from config.yaml.

2. Validation Layer
tools.validation.schema ensures data types and fields match the expected format.
This mirrors real-world bookkeeping ingestion requirements.

3. Analysis Layer
tools.analysis.tax applies Dutch VAT and KOR logic.
tools.analysis.bookkeeping aggregates categories and totals.

4. Orchestrator Layer
orchestrator.controller executes YAML-defined workflows,
calling agents and tools in the correct order.

5. Agent Layer
Reusable processors that execute pipeline steps (LLM-ready for the future).

6. Output Layer
Everything goes to workspace/:

logs/*.ndjson

reports/*.json

summaries

This makes the system auditable and reproducible.




