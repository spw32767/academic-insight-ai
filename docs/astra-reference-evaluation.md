# Astra reference evaluation (2026-09-23)

The reference at `evaluation/reference/astra-v1/reference.json` contains 163 classifications made by `gpt-6-astra` with medium reasoning effort from the original Scopus title, abstract, and author keywords. It is **model-authored, not expert-verified ground truth**. `split.json` records its SHA-256 digest and a deterministic 112/51 development/holdout split. Matching normalized titles or DOIs stay in the same partition. The source workbook SHA-256 is recorded in both files, and the evaluator rejects a mismatched workbook or changed reference. Change the `v1` directory name if a new reference is ever adopted; do not overwrite these files.

The `EDTECH_LEARNING_DIGITAL_LIBRARY` category has only one example, which landed in holdout. Its per-category result cannot establish generalization. The two `THEORETICAL_CS` examples were divided one per partition. All conclusions are limited by these very small supports and by the model-authored reference itself.

Run an existing checkpoint against the frozen reference:

```powershell
python scripts/evaluate_against_astra.py outputs/my-local-test/results.json --output outputs/astra-evaluation/legacy.json
```

The evaluator reports exact category agreement, agreement on reference-assigned records, false assignments on reference `Preface`, false reviews on reference-assigned records, confidently wrong assignments, a separate confidence agreement count, per-category precision/recall/F1, confusion pairs, and recorded runtime. It reports each partition separately. A matching category is an agreement with Astra, not proof of correctness; matching confidence labels do not make those probabilities calibrated.

The opt-in `astra_candidate` mode tests clearer boundaries between applied AI and AI methods and between network systems and their AI tools. The API default remains `legacy`. Run only the development partition while editing the candidate prompt:

```powershell
python scripts/classify_scopus_export.py C:\Users\aumki\Downloads\scopus_full_export_2026-09-15-15-07-38_v003.xlsx --verification-mode astra_candidate --split-manifest evaluation\reference\astra-v1\split.json --partition development --checkpoint outputs\astra-evaluation\candidate-development.json
python scripts/evaluate_against_astra.py outputs\astra-evaluation\candidate-development.json --output outputs\astra-evaluation\candidate-development-evaluation.json
```

After freezing the candidate prompt and version, run holdout once with a **different** checkpoint path and `--partition holdout`. Compare with the frozen legacy baseline, including runtime and confidently wrong assignments. Do not use holdout paper-specific discrepancies to tune the same version. If the candidate does not improve sufficiently, retain the legacy default and document the failure; do not deploy a lower-quality prompt by default.

## Completed local evaluation

All 163 original records were present in the earlier legacy checkpoint. The candidate was run once on the 112 development records, then once on the 51 holdout records. One holdout model response contained `Preface` and a non-null category; the candidate now clears that contradictory code and sends the item to review. The run resumed from its checkpoint without recomputing finished rows.

| Measure | Legacy development | Candidate development | Legacy holdout | Candidate holdout |
| --- | ---: | ---: | ---: | ---: |
| Same category as Astra | 78/112 (69.6%) | 81/112 (72.3%) | 29/51 (56.9%) | 32/51 (62.7%) |
| High confidence, different category | 32 | 31 | 22 | 18 |
| Assigned on reference Preface | 0 | 0 | 3 | 2 |
| Review on reference-assigned paper | 0 | 0 | 0 | 0 |
| Recorded processing time | 312.30 s | 476.11 s | 148.78 s | 388.15 s |

Across all records, the candidate agreed on 113/163 versus 107/163 for legacy, while taking 864.26 seconds versus 461.08 seconds. It still returned `High` for 148/163 records, including 49 that differed in category from the reference. Its confidence labels therefore remain uncalibrated. The holdout candidate runtime includes retries for the contradictory response; development time was already 52% longer than legacy. The candidate improved category agreement modestly but did not solve confidence quality and materially raised latency. **Decision: retain `legacy` as the API default; keep `astra_candidate` experimental and do not deploy it to the VM as a replacement.**

The largest remaining boundary is AI methods versus applied AI. The single EdTech example and two Theoretical CS examples cannot support a deployment claim for those categories. A next iteration should address confidence calibration and boundary examples on a new development version, then use a *new* sealed holdout or independently sourced records. Reusing these 51 holdout labels for tuning would erase their value as an independent check.

For VM deployment, first verify representative latency and throughput on the VM and fund-management API authentication/integration with a staging database. The evaluation here does not modify the database or Excel workbook.
