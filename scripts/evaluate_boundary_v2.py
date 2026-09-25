"""Compare v1 and v2 on the same development papers unseen in both prompts."""

import json
from pathlib import Path

from academic_insight_ai.tasks.article_classification.fewshot_examples import BOUNDARY_EXAMPLE_IDS, EXAMPLE_IDS
from evaluate_against_astra import _metrics, load_reference


def main() -> None:
    reference, split = load_reference(Path("evaluation/reference/astra-v1"))
    ids = set(split["development_ids"]) - EXAMPLE_IDS - BOUNDARY_EXAMPLE_IDS
    checkpoints = {
        "legacy": Path("outputs/my-local-test/results.json"),
        "fewshot_v1": Path("outputs/fewshot-v1/development.json"),
        "boundary_v2": Path("outputs/boundary-v2/development.json"),
    }
    results = {}
    for name, path in checkpoints.items():
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint["source_sha256"] != split["source_sha256"] or not ids <= set(checkpoint["results"]):
            raise ValueError(f"Incompatible or incomplete checkpoint: {name}")
        results[name] = _metrics(reference, checkpoint["results"], ids)
    output = {"note": "Astra agreement on development records unseen in both example sets, not expert accuracy.",
              "evaluated": len(ids), "results": results}
    path = Path("outputs/boundary-v2/development-evaluation.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {"category_exact": data["category_exact"],
                             "wrong_high": data["wrong_high"],
                             "seconds": data["runtime_seconds"]["total"]}
                      for name, data in results.items()}))


if __name__ == "__main__":
    main()
