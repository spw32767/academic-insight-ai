from academic_insight_ai.tasks.article_classification.runner import run_article_classification

TASK_RUNNERS = {
    "article-classification": run_article_classification,
}


def list_tasks() -> list[str]:
    return sorted(TASK_RUNNERS.keys())
