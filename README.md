# academic-insight-ai

`academic-insight-ai` is a local, CLI-first LLM workbench for academic data tasks.

Current focus:
- run repeatable AI tasks from local input files
- select local model from a shared registry
- validate structured output
- save timestamped outputs for review and comparison

What this project is not (yet):
- no web UI
- no API server
- no queue system
- no vector DB / RAG
- no direct database write-back

## Quick start

### 1) Python setup

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

### 2) Environment setup

```bash
copy .env.example .env
```

Default values:
- `OLLAMA_BASE_URL=http://localhost:11434`
- `DEFAULT_MODEL=phi3`
- `LOG_LEVEL=INFO`
- `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/academic_db`

### 3) Install Ollama (required)

Ollama must be installed separately from this project.

1. Download and install Ollama from https://ollama.com/download
2. Start Ollama so local API is available at `http://localhost:11434`
3. Verify Ollama is running:

```bash
ollama --version
```

If the command is not found, restart terminal after installation.

### 4) Pull your first model

```bash
ollama pull phi3
```

Optional additional models:

```bash
ollama pull gemma:2b
ollama pull qwen3:4b
```

## Run first task

Console script:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json
```

Or module execution:

```bash
python -m academic_insight_ai.cli.run_task run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json
```

Add limit and custom output path:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --limit 2 --output outputs/article-classification/manual_run_phi3.json
```

Separate smoke-test output from production output:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type smoke --limit 2
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table scopus_documents --db-id-column id --db-title-column title --db-abstract-column abstract --run-type production --limit 50
```

Include abstract in output (optional):

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type smoke --include-abstract --abstract-max-chars 500 --limit 2
```

Outputs are saved under:
- `outputs/article-classification/production/` (default)
- `outputs/article-classification/smoke/` (when `--run-type smoke`)

Run from MariaDB/MySQL (read-only input):

```bash
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table articles --db-id-column article_id --db-title-column title --db-abstract-column abstract --limit 50
```

Notes:
- `DATABASE_URL` must be set in `.env`
- DB input mode filters out rows where abstract is NULL or empty by default
- DB mode currently reads input records only; it does not write back to DB

Each output record also includes debug fields for traceability:
- `title` (source article title for easier verification with DB)
- `abstract` (optional, when `--include-abstract` is enabled)
- `debug_initial_prompt`
- `debug_correction_prompt` (present when retry is used)
- `raw_model_response`
- `confidence_source` (currently `model_reported`)
- `validation_error_type` (present when correction/failure path is used)

## Project layout

```txt
src/academic_insight_ai/
  cli/        # CLI command entrypoints
  core/       # shared config/logging/validation
  models/     # provider interfaces, Ollama provider, model registry
  tasks/      # task-specific implementations
  database/   # reserved for future DB integration
```

## Add a new task

1. Create a new folder under `src/academic_insight_ai/tasks/your_task_name/`
2. Keep prompt, categories/config, schema, and runner inside that folder
3. Add task runner to `src/academic_insight_ai/tasks/__init__.py`
4. Run via `academic-ai run-task --task your-task-name ...`

Rule: task-specific categories/prompts/schema stay inside that task folder.

## Add a new model

1. Edit `src/academic_insight_ai/models/registry.py`
2. Add a new logical ID mapped to provider and provider model name
3. Pull model in Ollama, for example:

```bash
ollama pull <model-name>
```

## Current limitations

- database mode is read-only input (no write-back yet)
- runs one model per command
- no parallel execution across models
- relies on model response correctness with one retry for schema correction

## Command reference

Common run commands are collected in `docs/run-commands.md`.
