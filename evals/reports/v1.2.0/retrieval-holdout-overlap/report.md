# RAG evaluation

- Task: retrieval
- Embedding: real; LLM: none
- Cases: 23; errors: 0
- Lexical/behavior diagnostics are proxies, not answer accuracy.
- null semantic metrics mean NOT EVALUATED; refusals do not earn full faithfulness.
- Histories are supplied fixtures, not a generated conversation rollout.

| Metric | Mean | Evaluated cases |
|---|---:|---:|
| context_precision_at_k | 0.2621 | 22 |
| evidence_recall_at_k | 0.8636 | 22 |
| mrr | 0.8409 | 22 |

## Cases needing review

- hotpot-5ac3165c5542995ef918c10a
- hotpot-5adf37a95542995ec70e8f97
- hotpot-5a74106b55429979e288289e
- hotpot-5abd94525542992ac4f382d2
- hotpot-5ae22b8d554299234fd0440f
