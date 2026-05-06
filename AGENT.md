# AGENT.md

## Project purpose

`academic-insight-ai` is a CLI-first local LLM workbench for academic data workflows.

The repository is designed to support multiple AI tasks over time (classification, extraction, summarization, etc.) while sharing a common model and runtime layer.

## Architecture rules

1. Keep shared/core code separate from task-specific code.
2. Shared code must not import task-specific modules.
3. Task code may import shared code.
4. Task-specific prompts/categories/schema must live inside each task folder.
5. Keep first implementation CLI-based (no web/API dashboard additions).
6. Do not create empty folders/files unless immediately used.

## Folder responsibilities

- `src/academic_insight_ai/core/`
  - config loading
  - logging setup
  - schema/JSON validation helpers

- `src/academic_insight_ai/models/`
  - provider abstractions and implementations
  - model registry (logical id -> provider model name)

- `src/academic_insight_ai/tasks/`
  - task folders with self-contained logic per task

- `src/academic_insight_ai/database/`
  - future database integration only

- `tests/fixtures/`
  - local sample input payloads for task runs

- `outputs/`
  - runtime task outputs (gitignored)

## Task creation pattern

For each new task, add a folder in `src/academic_insight_ai/tasks/<task_name>/` and include only files needed for the task.

Recommended pattern:
- `config.py` (task constants/categories)
- `prompt.py` (prompt builders)
- `schema.py` (pydantic models)
- `runner.py` (task execution)
- `README.md` (task notes)

Then register the task runner in `src/academic_insight_ai/tasks/__init__.py`.

## Model provider pattern

1. Add provider implementation in `src/academic_insight_ai/models/providers/`
2. Keep provider interface consistent with `BaseModelProvider.generate(...)`
3. Register logical model IDs in `src/academic_insight_ai/models/registry.py`
4. Keep provider-specific configuration in shared config/env layer

## Coding style

- Python 3.10+
- type hints required for public functions
- use pydantic for runtime data validation where needed
- prefer small, readable modules
- minimal dependencies
- no hardcoded absolute paths
- no secrets in repo

## What not to modify carelessly

- task ownership boundaries (do not move task prompts/schema to global config)
- CLI command contract unless requirement changes
- model registry structure without migration notes

## What not to add prematurely

Do not introduce in early phases unless explicitly requested:
- web UI
- API server
- RAG/vector DB
- queue system
- fine-tuning pipeline
- dockerized orchestration
