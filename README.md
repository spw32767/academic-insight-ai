# academic-insight-ai

`academic-insight-ai` is a local LLM workbench and API service for academic data tasks.

Current focus:
- run repeatable AI tasks from local input files
- select local model from a shared registry
- validate structured output
- save timestamped outputs for review and comparison

What this project is not:
- no web UI
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

## Run the independent APIs

For installation alongside an existing fund-management deployment on Windows Server, follow the [Windows VM deployment guide](docs/windows-vm-deployment.md).

The PDF/OCR reader and article classifier are separate processes and never call each other.

```bash
academic-reader-api          # defaults to 127.0.0.1:8102
academic-classification-api  # defaults to 127.0.0.1:8101
```

Set the same `AI_API_KEY` in this service and its caller. The reader exposes
`POST /v1/papers/extract` and `POST /v1/papers/summarize`; the classifier exposes
`POST /v1/papers/classify`. Scanned PDFs require OCRmyPDF with the `tha` and `eng`
Tesseract language packs. Each service has its own `/health` endpoint and model setting.
The reader returns publication month, volume/issue, and page numbers only when it can
verify them in the PDF. It rejects documents that do not resemble a research paper.
For an English abstract, send `{"abstract":"...","include_translation":true}` to
`/v1/papers/summarize` to receive both `summary_th` and `translation_th`; the
original abstract remains available in the extract response.

The classifier selects one of the seven active categories supplied by fund-management when there is enough evidence. The API
defaults to the original `legacy` mode while the newer evidence-based approaches are evaluated. Set `verification_mode` to
`single` to require an exact supporting quote from the abstract (or fallback text). Set it to `evidence_agreement` to run
a second independent assessment; that conservative
experimental mode assigns a category only when both passes agree. Its confidence is the lower of the two model ratings.
Neither confidence nor agreement is a calibrated accuracy score. Missing evidence, non-research records, and disagreement
in agreement mode return a null category and `Preface` for review. The additive response fields `evidence_quote`, `evidence_source`,
`primary_contribution`, `verification_status`, `candidate_category_codes`, and `assessments` provide an audit trail.

To classify a Scopus Excel export locally without fetching PDFs or opening the `scopus_link`, install
`pip install -e ".[scopus-export]"` and run `python scripts/classify_scopus_export.py "C:\path\export.xlsx"`.
The script reads `abstract`, `title`, and `authkeywords` and saves a resumable, classifier-versioned JSON checkpoint without
modifying the source workbook. It will not resume an older classifier's checkpoint. The classification API itself does not require `openpyxl`.
Compare it with an earlier run using
`python scripts/evaluate_classification_checkpoint.py outputs/my-local-test/results.json outputs/evidence-agreement/checkpoint.json --output outputs/evidence-agreement/evaluation.json`.
This reports agreement and processing time; agreement between two model runs is not an accuracy score.
The batch script defaults to the experimental `evidence_agreement` mode; pass `--verification-mode single`
or `--verification-mode legacy` with a separate checkpoint path to compare modes.
The frozen Astra model-authored reference, duplicate-aware development/holdout split, comparison commands,
and limitations are documented in [the reference evaluation](docs/astra-reference-evaluation.md).
The opt-in `astra_candidate` prompt can be evaluated by partition; it is not the API default.
The later opt-in `fewshot_candidate` experiment uses eight frozen development examples. Its
[evaluation and commands](docs/fewshot-classifier-evaluation.md) compare the same unseen records
against the earlier local runs.
An [independent 130-paper evaluation](docs/new-scopus-evaluation.md) compares legacy, few-shot v1,
and the opt-in `boundary_candidate` prompt on a new Scopus export. The boundary prompt improves
the targeted AI/Applied cases but reduces agreement on a random sample, so it is not the default.
Its operational High ratings are capped at Medium as a temporary precaution, not statistical calibration.
The classification request may also set `confidence_policy` to `conservative_cap` independently of
`verification_mode`; this preserves the selected category and the model's raw rating in
`model_reported_confidence`, while returning at most `Medium` as the operational confidence.
The default `model_reported` policy preserves existing API behavior.

For a model-quality test, the fund-management frontend and backend are not required. Ensure Ollama is running (`ollama list`); start `ollama serve` only if it is stopped. Then run
the reader, Thai summarizer, and classifier directly against one or more PDFs:

```powershell
python scripts/test_real_papers.py "C:\path\paper-1.pdf" "C:\path\paper-2.pdf" --model qwen3-4b
```

The command prints the duration of each stage and writes the extracted metadata, Thai summary, classification,
and confidence to `outputs/manual-paper-test/results.json`. Start the two APIs and the fund-management apps only
after this direct test passes and you need to verify the complete upload, DOI mapping, database, and form flow.

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
