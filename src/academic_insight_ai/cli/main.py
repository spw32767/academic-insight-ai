from __future__ import annotations

from pathlib import Path

import typer

from academic_insight_ai.core.config import load_config
from academic_insight_ai.core.logging import configure_logging
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
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False, readable=True),
    output_path: Path | None = typer.Option(None, "--output", help="Optional output JSON path"),
    limit: int | None = typer.Option(None, "--limit", min=1),
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

    try:
        written_path = runner(
            input_path=input_path,
            model_name=model_spec.provider_model_name,
            provider=provider,
            output_path=output_path,
            limit=limit,
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
