# RAG evaluation

- Task: e2e
- Embedding: real; LLM: real
- Cases: 60; errors: 0
- Lexical/behavior diagnostics are proxies, not answer accuracy.
- null semantic metrics mean NOT EVALUATED; refusals do not earn full faithfulness.
- Histories are supplied fixtures, not a generated conversation rollout.

| Metric | Mean | Evaluated cases |
|---|---:|---:|
| answer_token_f1 | 0.2546 | 54 |
| behavior_match_heuristic | 0.8667 | 60 |
| behavior_match_judged | 0.8833 | 60 |
| citation_coverage | 0.9033 | 56 |
| citation_id_validity | 1.0000 | 54 |
| citation_support | 0.9815 | 54 |
| completeness | 0.8667 | 60 |
| context_precision_at_k | 0.2660 | 54 |
| contradiction_rate | 0.0238 | 56 |
| evidence_recall_at_k | 0.8704 | 54 |
| faithfulness | 0.9568 | 56 |
| forbidden_fact_count | 0.0000 | 60 |
| inappropriate_answer | 0.0000 | 5 |
| inappropriate_refusal | 0.0926 | 54 |
| mrr | 0.8525 | 54 |
| required_fact_coverage | 0.7963 | 54 |
| semantic_correctness | 0.8667 | 60 |
| unsupported_claim_rate | 0.0193 | 56 |

## Cases needing review

- xquad-572a005f1d046914007796b8
- xquad-571cbe35dd7acb1400e4c13d
- hotpot-5adf37a95542995ec70e8f97
- hotpot-5ae33c4d5542992f92d82262
- hotpot-5a85b2d95542997b5ce40028
- hotpot-5a74106b55429979e288289e
- hotpot-5adc53f75542996e6852530a
- hotpot-5ae6050f55429929b0807a5e
- hotpot-5ae7e1fc55429952e35ea9cc
- hotpot-5a713ea95542994082a3e6e4
- hotpot-5ab3b0bf5542992ade7c6e39
- hotpot-5ae22b8d554299234fd0440f
- hotpot-5ae005b555429942ec259bec
- xquad-57302bd0b2c2fd14005689dc
- hotpot-5ae32e125542991a06ce9946
