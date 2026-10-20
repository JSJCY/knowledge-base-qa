# RAG evaluation

- Task: retrieval
- Embedding: real; LLM: none
- Cases: 37; errors: 0
- Lexical/behavior diagnostics are proxies, not answer accuracy.
- null semantic metrics mean NOT EVALUATED; refusals do not earn full faithfulness.
- Histories are supplied fixtures, not a generated conversation rollout.

| Metric | Mean | Evaluated cases |
|---|---:|---:|
| context_precision_at_k | 0.2375 | 32 |
| evidence_recall_at_k | 0.8125 | 32 |
| mrr | 0.8047 | 32 |

## Cases needing review

- hotpot-5ae33c4d5542992f92d82262
- hotpot-5a85b2d95542997b5ce40028
- hotpot-5ae32e125542991a06ce9946
- hotpot-5adc53f75542996e6852530a
- hotpot-5ae6050f55429929b0807a5e
- hotpot-5ae7e1fc55429952e35ea9cc
- hotpot-5a713ea95542994082a3e6e4
- hotpot-5ab3b0bf5542992ade7c6e39
- hotpot-5ae005b555429942ec259bec
