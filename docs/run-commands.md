# Run Commands

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
```

## Quick reference

Notes:
- `--abstract-max-chars` requires `--include-abstract`
- `--input` is required only when `--input-source file`
- DB mode needs `DATABASE_URL` in `.env`

Command pattern:

```bash
academic-ai run-task \
  --task article-classification \
  --model <phi3|gemma|qwen3-4b> \
  --input-source <file|db> \
  [--input <json-file-when-file-mode>] \
  [--db-table <table>] [--db-id-column <id-col>] [--db-title-column <title-col>] [--db-abstract-column <abstract-col>] \
  [--db-require-non-empty-abstract|--db-allow-empty-abstract] \
  [--include-abstract|--no-include-abstract] [--abstract-max-chars <N>] \
  [--run-type <smoke|production>] \
  [--limit <N>] \
  [--output <custom-output-path.json>]
```

## Smoke commands

Smoke with file input:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type smoke --limit 2
```

Smoke with file input and full abstract in output:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type smoke --include-abstract --limit 2
```

Smoke with file input and truncated abstract in output:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type smoke --include-abstract --abstract-max-chars 500 --limit 2
```

Smoke with DB input:

```bash
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table scopus_documents --db-id-column id --db-title-column title --db-abstract-column abstract --run-type smoke --limit 5
```

## Production commands

Production with file input:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --run-type production --limit 50
```

Production with DB input:

```bash
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table scopus_documents --db-id-column id --db-title-column title --db-abstract-column abstract --run-type production --limit 50
```

Production with DB input and truncated abstract in output:

```bash
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table scopus_documents --db-id-column id --db-title-column title --db-abstract-column abstract --run-type production --include-abstract --abstract-max-chars 600 --limit 50
```

Production with DB input allowing empty abstracts:

```bash
academic-ai run-task --task article-classification --model phi3 --input-source db --db-table scopus_documents --db-id-column id --db-title-column title --db-abstract-column abstract --db-allow-empty-abstract --run-type production --limit 50
```

## Utility commands

Custom output file path:

```bash
academic-ai run-task --task article-classification --model phi3 --input tests/fixtures/sample_articles.json --output outputs/article-classification/manual/custom_run_phi3.json --limit 10
```

Try another local model:

```bash
academic-ai run-task --task article-classification --model qwen3-4b --input tests/fixtures/sample_articles.json --run-type smoke --limit 5
```
