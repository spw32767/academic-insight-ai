# Independent Scopus prompt evaluation (2026-09-23)

The August Scopus export supplied 565 eligible records after excluding overlaps with the September evaluation workbook by Scopus ID, normalized title, or DOI, plus duplicates within the August export. `scripts/prepare_new_scopus_eval.py` froze 100 randomly sampled records and 30 additional AI Algorithms / Applied AI boundary challenges. The selection and source checksum are in `evaluation/new-scopus-v1/manifest.json`. The source record snapshot is kept locally under `outputs/new-scopus-v1/` because exports can contain publication data and are not committed.

An independent Astra medium pass labeled all 130 records from titles, abstracts, and keywords **before viewing any Qwen predictions**. Its rationale and exact evidence excerpts are in `evaluation/new-scopus-v1/reference.json`; `reference.sha256` detects edits. This is a model-authored reference, **not expert ground truth**. Treat agreement as agreement with Astra's interpretation of the seven-category rubric, not measured real-world accuracy. The 30 challenge records were deliberately enriched for the AI/Applied boundary and are not representative of normal workload.

| Prompt (`qwen3-4b`) | Random 100 category matches | Challenge 30 matches | All 130 | Classification errors | Raw model High with wrong category, all 130 | Runtime, all 130 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Legacy | 58 | 21 | 79 | 0 | 46 | 390 s |
| Few-shot v1 | **70** | 16 | 86 | 1 | 43 | **256 s** |
| Boundary v2 | 63 | **25** | 88 | 3 | 40 | 289 s |

Classification errors mean the model returned an invalid category even after retries; they are separate from legitimate `Preface` judgments. Boundary v2's operational confidence is capped at Medium, so its displayed `wrong_high` count of zero is a policy effect. Its **raw** model output was High for 127/130 records, and 40 of those category choices disagreed with the Astra reference. Few-shot v1 returned High for 129/130 records, with 43 disagreements. These High labels are plainly not calibrated probabilities. The runner records both the model rating and the operational rating for v2.

On the representative random sample, v2 fixed 10 v1 disagreements but changed 17 v1 matches into disagreements. On the enriched challenge set, it fixed 10 and regressed 1. This boundary prompt improves the specific boundary but harms the broader sample; do **not** replace v1 with v2 globally. V1 improves the random sample over legacy and is faster, but one invalid output and 29 wrong High judgments in the random sample make automatic, unreviewed database writes premature. No model weights were trained in this experiment. The 130 new Astra labels are also imbalanced: no Quantum Information examples, only eight EdTech examples, and five `Preface` records. Repeatedly tuning on these 130 records would contaminate this test and overfit another model's decisions.

Recommended next iteration: keep `legacy` as the production API default for now and retain `fewshot_candidate` and `boundary_candidate` as opt-in experiments. The API request can use `confidence_policy: "conservative_cap"` independently of the prompt to preserve the chosen category and return at most Medium, with the raw rating retained in `model_reported_confidence`. This is a temporary policy, not calibrated confidence. Route invalid responses, missing evidence, and `Preface` to review. Collect a **new** frozen sample that includes all seven categories and sparse/empty records, and have a knowledgeable reviewer adjudicate at least a small disagreement set if one becomes available. Re-evaluate any prompt, model, or fine-tune on that new sample once. Only consider LoRA/QLoRA training after a larger, balanced, stable reference and a clean untouched holdout exist; do not train repeatedly against this test set.

Reproduce the local evaluation with the August workbook in Downloads (the source snapshot can be rebuilt with `scripts/prepare_new_scopus_eval.py`):

```powershell
python scripts/classify_selected_scopus.py --mode legacy --checkpoint outputs/new-scopus-v1/legacy.json
python scripts/classify_selected_scopus.py --mode fewshot_candidate --checkpoint outputs/new-scopus-v1/fewshot-v1.json
python scripts/classify_selected_scopus.py --mode boundary_candidate --checkpoint outputs/new-scopus-v1/boundary-v2.json
python scripts/evaluate_new_scopus.py outputs/new-scopus-v1/legacy.json outputs/new-scopus-v1/fewshot-v1.json outputs/new-scopus-v1/boundary-v2.json --output outputs/new-scopus-v1/evaluation.json
```

Runs are resumable and should execute sequentially against Ollama. Detailed per-category confusion, the random/challenge split, confidence distributions, and per-record disagreements are in the locally generated `outputs/new-scopus-v1/evaluation.json`.
