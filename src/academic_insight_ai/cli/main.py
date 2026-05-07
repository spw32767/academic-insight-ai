from __future__ import annotations

from pathlib import Path
from datetime import datetime

import typer

from academic_insight_ai.core.config import load_config
from academic_insight_ai.core.logging import configure_logging
from academic_insight_ai.database.mysql_reader import fetch_articles_from_mysql
from academic_insight_ai.models.providers.ollama import OllamaProvider
from academic_insight_ai.models.registry import get_model_spec, list_models
from academic_insight_ai.tasks import TASK_RUNNERS, list_tasks

app = typer.Typer(help="Academic Insight AI CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """CLI entrypoint group."""


@app.command("run-task")
def run_task(
    task: str = typer.Option(..., "--task", help="Task name, e.g. article-classification"),
    model: str | None = typer.Option(None, "--model", help="Logical model id from registry"),
    input_source: str = typer.Option("file", "--input-source", help="file or db"),
    input_path: Path | None = typer.Option(None, "--input", exists=True, dir_okay=False, readable=True),
    output_path: Path | None = typer.Option(None, "--output", help="Optional output JSON path"),
    run_type: str = typer.Option(
        "production",
        "--run-type",
        help="Output grouping for default path: production or smoke",
    ),
    limit: int | None = typer.Option(None, "--limit", min=1),
    db_table: str = typer.Option("articles", "--db-table", help="Source table name"),
    db_id_column: str = typer.Option("article_id", "--db-id-column", help="Article id column"),
    db_title_column: str = typer.Option("title", "--db-title-column", help="Article title column"),
    db_abstract_column: str = typer.Option("abstract", "--db-abstract-column", help="Article abstract column"),
    db_require_non_empty_abstract: bool = typer.Option(
        True,
        "--db-require-non-empty-abstract/--db-allow-empty-abstract",
        help="Filter rows where abstract is NULL or empty",
    ),
    include_abstract: bool = typer.Option(
        False,
        "--include-abstract/--no-include-abstract",
        help="Include source abstract in output records",
    ),
    abstract_max_chars: int | None = typer.Option(
        None,
        "--abstract-max-chars",
        min=1,
        help="Optional abstract length cap when --include-abstract is enabled",
    ),
) -> None:
    config = load_config()
    configure_logging(config.log_level)

    if task not in TASK_RUNNERS:
        typer.echo(f"Unknown task '{task}'. Available tasks: {', '.join(list_tasks())}")
        raise typer.Exit(code=2)

    model_id = model or config.default_model
    try:
        model_spec = get_model_spec(model_id)
    except ValueError as exc:
        typer.echo(str(exc))
        typer.echo(f"Available models: {', '.join(list_models())}")
        raise typer.Exit(code=2)

    if model_spec.provider != "ollama":
        typer.echo(f"Unsupported provider: {model_spec.provider}")
        raise typer.Exit(code=2)

    provider = OllamaProvider(base_url=config.ollama_base_url)
    runner = TASK_RUNNERS[task]

    db_records: list[dict] | None = None
    normalized_source = input_source.lower().strip()
    if normalized_source not in {"file", "db"}:
        typer.echo("--input-source must be 'file' or 'db'")
        raise typer.Exit(code=2)

    if normalized_source == "file" and input_path is None:
        typer.echo("--input is required when --input-source file")
        raise typer.Exit(code=2)

    if normalized_source == "db":
        if not config.database_url:
            typer.echo("DATABASE_URL is not set. Configure it in .env first.")
            raise typer.Exit(code=2)
        try:
            db_records = fetch_articles_from_mysql(
                database_url=config.database_url,
                table=db_table,
                id_column=db_id_column,
                title_column=db_title_column,
                abstract_column=db_abstract_column,
                limit=limit,
                require_non_empty_abstract=db_require_non_empty_abstract,
            )
        except Exception as exc:
            typer.echo(f"Failed to read input from database. Details: {exc}")
            raise typer.Exit(code=1)

    normalized_run_type = run_type.lower().strip()
    if normalized_run_type not in {"production", "smoke"}:
        typer.echo("--run-type must be 'production' or 'smoke'")
        raise typer.Exit(code=2)

    if abstract_max_chars is not None and not include_abstract:
        typer.echo("--abstract-max-chars requires --include-abstract")
        raise typer.Exit(code=2)

    computed_output_path = output_path
    if computed_output_path is None:
        out_dir = Path("outputs") / "article-classification" / normalized_run_type
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        computed_output_path = out_dir / f"{timestamp}_{model_id}.json"

    try:
        written_path = runner(
            input_path=input_path,
            model_name=model_spec.provider_model_name,
            provider=provider,
            output_path=computed_output_path,
            limit=limit,
            input_records=db_records,
            include_abstract=include_abstract,
            abstract_max_chars=abstract_max_chars,
        )
    except Exception as exc:
        typer.echo(
            "Task execution failed. Ensure Ollama is running and model is pulled. "
            f"Details: {exc}"
        )
        raise typer.Exit(code=1)

    typer.echo(f"Task completed. Output saved to: {written_path}")


if __name__ == "__main__":
    app()
