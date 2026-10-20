import pytest

from app.evaluation.judge import Verdict, apply_verdict
from tests.test_evaluation_metrics import example


def row(answer="Python [S1]"):
    return {"case":example().model_dump(),"answer":answer,
            "retrieved":[{"document_key":"d","source_spans":[[0,6]]}],
            "citations":[{"source_id":1}]}


def verdict(**kwargs):
    return Verdict(correctness=2,completeness=2,behavior_match=True,reason="reference matches",claims=kwargs.get("claims",[]))


def test_judge_no_claims_keeps_faithfulness_undefined():
    scores=apply_verdict(row("Insufficient evidence"),verdict())
    assert scores["faithfulness"] is None
    assert scores["citation_support"] is None


def test_judge_cannot_invent_citation_ids():
    v=verdict(claims=[{"text":"Python","status":"supported","cited_source_ids":[9],"citation_supported":True,"reason":"x"}])
    with pytest.raises(ValueError,match="invented"):
        apply_verdict(row(),v)


def test_judge_tracks_supported_claims_and_missing_citations_separately():
    v=verdict(claims=[{"text":"Python","status":"supported","cited_source_ids":[],"citation_supported":False,"reason":"source supports"}])
    scores=apply_verdict(row("Python"),v)
    assert scores["faithfulness"]==1
    assert scores["citation_coverage"]==0
    assert scores["citation_support"] is None
