# Evidence and agreement classifier experiment (2026-09-22)

The seven-category classifier has experimental modes that check whether each assigned category has a short, exact quote from the supplied abstract or fallback text. The API retains its original `legacy` behavior by default. The opt-in `single` mode adds quote validation. The opt-in `evidence_agreement` mode asks the same local model a second time with a different framing and reversed taxonomy order, then assigns a category only when both choices match. A disagreement returns a null category and `Preface` for review. This is a consistency check, not an independent expert or accuracy measurement.

We ran `qwen3-4b` locally over all 163 rows of `scopus_full_export_2026-09-15-15-07-38_v003.xlsx` in agreement mode. The checkpoint is `outputs/evidence-agreement/checkpoint.json`; the reproducible comparison is `outputs/evidence-agreement/evaluation.json`. These output files are local and excluded from Git.
That long run started before the per-pass `assessments` field was added to checkpoints, so its rows include candidate codes but not both full pass explanations. A later one-row smoke test in `outputs/evidence-agreement/agreement-demo.json` verifies the final response shape.

| Measure | Earlier one-pass run | Evidence-agreement experiment |
| --- | ---: | ---: |
| Rows | 163 | 163 |
| Assigned category | 150 | 77 |
| `Preface` / review | 13 | 86 |
| Model-pass disagreements | Not measured | 72 |
| Unverifiable model evidence | Not measured | 3 |
| Total recorded processing time | 461.08 s | 978.93 s |

The `single` evidence-quote mode was then run on all 163 rows. It assigned 149 categories and returned 14 `Preface` results (11 publication-type rules and three invalid model-evidence outputs). Every assigned row had an exact source quote, yet all 149 assigned rows were still rated `High` by the model. It took 466.64 seconds, close to the earlier one-pass run. Among the 147 rows assigned in both one-pass runs, 98 category choices matched and 49 changed. The SERS chemistry paper at row 31 was incorrectly assigned to Computer Engineering, and the cardiac-modeling paper at row 156 was incorrectly assigned to Theoretical CS, both with `High` confidence. The full single-mode checkpoint and comparison are `outputs/evidence-agreement/single-checkpoint.json` and `outputs/evidence-agreement/single-evaluation.json`.

Of the 72 disagreements, 59 were between `AI_ALGORITHMS` and `APPLIED_AI`. The 77 assigned categories all received `High` from both passes; this must not be interpreted as 100% certainty. Among the 77 rows assigned in both runs, 55 categories matched the earlier run and 22 differed. Neither run is a verified answer key, so those differences cannot establish which one is correct. The new run correctly avoided confirming `QUANTUM_INFORMATION` for previously suspicious rows 58 and 93 and left outside-taxonomy examples such as rows 31 and 156 for review.

The agreement mode reduced coverage too much and more than doubled runtime, so it remains opt-in. The single mode kept coverage and speed but changed many category decisions and made clear mistakes with High confidence, so it also remains opt-in. An exact quote establishes source provenance, not the correctness of the category. Before deploying to the university VM, tighten the boundary between new AI methods and applied AI, and define exclusions for scientific papers outside the seven computing categories. Explicit taxonomy examples or a stronger independent reviewer may help, but their outputs still need auditing. Without expert-labeled examples, report coverage, evidence validity, and stability rather than accuracy.
