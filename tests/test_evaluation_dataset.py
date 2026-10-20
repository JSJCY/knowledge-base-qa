from collections import Counter
from pathlib import Path

from app.evaluation.dataset import load_dataset


def test_dataset_has_valid_evidence_and_expected_slices():
    docs, cases = load_dataset(Path("evals/data"))
    assert Counter(case.dataset for case in cases) == {"xquad_zh":20, "hotpotqa":20, "project":20}
    assert docs
    assert {case.split for case in cases} == {"dev", "holdout"}
    assert {"answer", "partial", "refuse", "clarify"} <= {case.expected_behavior for case in cases}
    assert any(case.history for case in cases)
    for case in cases:
        assert case.annotation
        for evidence in case.evidence:
            assert docs[evidence.document_id].text[evidence.start:evidence.end] == evidence.text
