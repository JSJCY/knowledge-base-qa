# Evaluation data attribution

The application remains MIT licensed. The derived evaluation data containing
XQuAD / HotpotQA excerpts is distributed under CC BY-SA 4.0:
https://creativecommons.org/licenses/by-sa/4.0/

- XQuAD: Mikel Artetxe, Sebastian Ruder, Dani Yogatama (2019), On the Cross-lingual
  Transferability of Monolingual Representations. https://github.com/google-deepmind/xquad
- HotpotQA: Zhilin Yang, Peng Qi, Saizheng Zhang et al. (2018), HotpotQA:
  A Dataset for Diverse, Explainable Multi-hop Question Answering. https://hotpotqa.github.io/
- Project scenarios: Codex-authored synthetic fixtures, pending independent human
  review. Released under CC BY-SA 4.0 alongside this collection.

Changes: selected 20 distinct Chinese paragraphs and one question each, and 20
HotpotQA validation questions from the first 100 publicly served records, using
seed 20261020; converted fields, added IDs, evidence offsets, development/holdout
assignments, and 20 synthetic project cases. This is a small derived smoke
benchmark, not an official benchmark score or human acceptance.

No Kaggle credentials are required. HotpotQA came from the maintainer's Hugging
Face dataset server because the CMU download was unavailable. The Kaggle mirror
is a discovery link, not the actual download source.
