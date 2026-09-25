# Few-shot classifier experiment (2026-09-23)

The opt-in `fewshot_candidate` mode adds eight short examples from the frozen Astra v1 **development** partition to the seven-category classifier prompt. The examples cover AI methods, applied AI, network systems, hardware, and a retraction notice. Their IDs and labels are checked against the frozen reference by `scripts/prepare_fewshot_pilot.py`. The frozen pilot manifest at `evaluation/fewshot-v1/manifest.json` selects 30 different development records. No example ID or duplicate title is in the pilot. The batch runner also excludes all eight example IDs when running the full development partition. The 51 holdout labels were not used for prompt selection or this experiment.

Run or resume the pilot locally:

```powershell
python scripts/prepare_fewshot_pilot.py
python scripts/classify_scopus_export.py C:\Users\aumki\Downloads\scopus_full_export_2026-09-15-15-07-38_v003.xlsx --verification-mode fewshot_candidate --split-manifest evaluation\reference\astra-v1\split.json --partition development --pilot-manifest evaluation\fewshot-v1\manifest.json --checkpoint outputs\fewshot-v1\pilot.json
python scripts/evaluate_fewshot_pilot.py
```

The full development run uses the same command without `--pilot-manifest`, with a different checkpoint path. The evaluator accepts `--scope development --fewshot outputs/fewshot-v1/development.json --output outputs/fewshot-v1/development-evaluation.json`. These output checkpoints and reports stay local in the ignored `outputs` directory. The original workbook is unchanged.

| Comparison | Legacy | Boundary prompt | Few-shot prompt |
| --- | ---: | ---: | ---: |
| Pilot agreement with Astra, 30 records | 19/30 | 19/30 | 21/30 |
| Pilot `High` with different category | 10 | 11 | 9 |
| Pilot recorded time | 96.37 s | 147.47 s | 78.44 s |
| Development agreement, 104 unseen records | 72/104 | 75/104 | 76/104 |
| Development `High` with different category | 30 | 29 | 28 |
| Development recorded time | 292.29 s | 449.30 s | 169.23 s |

The few-shot pilot gave identical categories on all 30 records when rerun as part of the full development batch. The prompt produced `High` for 94/104 development records; 28 of those disagree with Astra. Its largest error moved in the opposite direction from the legacy prompt: 18 Astra `AI_ALGORITHMS` records were assigned `APPLIED_AI`. Thus example-based prompting modestly improves category agreement while leaving confidence and the AI boundary unresolved. The recorded runtime comparison includes checkpoints from different earlier runs and may reflect model loading or provider changes, so it is not a controlled speed benchmark.

Afterward, a paired local check ran both `legacy` and `fewshot_candidate` on the same 12 pilot records with alternating order, after model warm-up. The temporary script and result are in ignored `outputs/fewshot-v1/paired_benchmark.py` and `paired-benchmark.json`. Legacy averaged 3.95 seconds (median 3.43), few-shot 2.04 seconds (median 2.03). Legacy explanations averaged 1,122 characters, few-shot 579, while prompt lengths for a short abstract were similar (about 4.8K characters). Shorter generated answers plausibly explain much of the latency difference. Few-shot agreed with Astra on 9/12 versus 6/12 for legacy in this small paired check. These figures describe one local sequential run; they are not a VM throughput guarantee.

**Decision:** keep `fewshot_candidate` opt-in. Do not promote it to the API default or use `High` for automatic acceptance. The 51 previously inspected holdout records would no longer be a blind final test for a new prompt. Before production selection, obtain an independently sourced evaluation set, assess per-category coverage, and separately test confidence handling. The current 4B prompt result alone does not justify changing the fund-management integration or VM deployment.

An 8B Qwen3 model was considered for a small local comparison, but it was not installed or run: the approximately 5.2 GB download was transferring at roughly 3 MB/s and estimated almost half an hour. This experiment therefore makes no quality or latency claim about 8B.
