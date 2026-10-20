# RAG evaluation

- Task: retrieval
- Embedding: real; LLM: none
- Cases: 23; errors: 0
- Lexical/behavior diagnostics are proxies, not answer accuracy.
- null semantic metrics mean NOT EVALUATED; refusals do not earn full faithfulness.
- Histories are supplied fixtures, not a generated conversation rollout.

| Metric | Mean | Evaluated cases |
|---|---:|---:|
| context_precision_at_k | 0.2894 | 22 |
| evidence_recall_at_k | 0.9242 | 22 |
| mrr | 0.8750 | 22 |

## Cases needing review

- hotpot-5adf37a95542995ec70e8f97
- hotpot-5a74106b55429979e288289e
- hotpot-5ae22b8d554299234fd0440f
