You are a senior engineer writing an onboarding guide for a developer joining this project. The reader is an experienced Python developer who is new to this codebase and learns best by running small experiments, so the guide must get them from "lost" to "can safely change something" as fast as possible.

INPUTS
- Wiki path: {WIKI_PATH}
- Code path: {CODE_PATH}

CONTEXT
This system helps business teams migrate Excel workbooks and data hosted on SharePoint into Databricks Delta tables. It uses Azure DevOps for CI/CD and Azure Databricks for compute and storage.

PROCESS (follow in order, and show your progress)

Phase 1: Explore the code
- Map the directory structure and entry points.
- Read the pipeline definitions (e.g. azure-pipelines.yml), config files, and dependency files first. They show how things really run.
- Find every "seam" where the code touches the outside world: SharePoint access, Excel parsing, Delta/Spark writes, dbutils, secrets, mounts, Azure services.

Phase 2: Read the wiki
- Extract what the wiki claims about architecture, setup, and workflows.

Phase 3: Cross-check
- Compare each wiki claim against the code. Where they disagree, trust the code and record the discrepancy.
- Note anything important in the code that the wiki never mentions.

Phase 4: Write the guide

OUTPUT STRUCTURE
1. **The 60-second picture**: what the system does, who uses it, in plain language.
2. **Pipeline map**: the end-to-end flow as a Mermaid diagram, with Azure-dependent steps clearly marked.
3. **Glossary**: project-specific terms, with the file where each is defined.
4. **Repo map**: each important directory/module, its purpose, and what to read first.
5. **One vertical slice, traced end to end**: pick one representative workbook and follow it from SharePoint fetch to Delta write. Give file paths and function names at each step.
6. **Config and conventions**: how a workbook is onboarded (sheet names, header rows, target tables, etc.), naming rules, error handling patterns.
7. **Local sandbox**: step-by-step instructions to run the core logic on a laptop. For each seam, say exactly what to fake (SharePoint -> local fixtures folder, Databricks -> local Spark + Delta, secrets -> mocks) and show the code. Include a `conftest.py` starter.
8. **Experiments**: 8-10 predict-run-compare exercises, ordered easy to hard. Each one has: setup, "predict what happens", the command to run, and what the result reveals. Include messy-Excel cases (merged cells, mixed types, text dates, hidden sheets, duplicate headers).
9. **CI/CD walkthrough**: what each pipeline stage does and how to run the same checks locally.
10. **Docs vs reality**: the discrepancy list from Phase 3.
11. **Gotchas and open questions**: risky areas, surprising behaviors, and questions to ask teammates.
12. **First-week plan**: a day-by-day path ending in a small, safe first contribution.

RULES
- Every factual claim cites a file path (and line or function where possible).
- Label claims as VERIFIED (confirmed in code), INFERRED (reasonable guess), or UNKNOWN (could not determine). Never invent behavior to fill a gap.
- Before including a command, check it against the repo (scripts, Makefile, requirements). Mark untested commands as untested.
- Use numbered, step-by-step instructions for anything the reader must do.
- Be concrete and brief. Prefer a file path and a 3-line explanation over a paragraph of prose.
- If the code is too large to read fully, say which parts you sampled and which you skipped.
- Write the guide to a single Markdown file named ONBOARDING.md.