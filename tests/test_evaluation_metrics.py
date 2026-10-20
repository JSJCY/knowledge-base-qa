from app.evaluation.dataset import Case, Evidence
from app.evaluation.metrics import fact_present, overlap_f1, score


def example():
    return Case(id="c",dataset="test",language="en",scenario="answer",group_id="g",split="dev",
                question="Language?",reference_answer="Python",expected_behavior="answer",document_ids=["d"],
                evidence=[Evidence(document_id="d",start=0,end=6,text="Python")],
                required_facts=["Python"],forbidden_facts=["Java"],annotation="fixture")


def test_wrong_nonempty_answer_fails_fact_diagnostics():
    result=score(example(),"Java",[],[])
    assert result["required_fact_coverage"]==0
    assert result["forbidden_fact_count"]==1
    assert result["faithfulness"] is None


def test_refusals_do_not_get_perfect_faithfulness():
    result=score(example(),"Insufficient information",[],[])
    assert result["behavior_match_heuristic"]==0
    assert result["faithfulness"] is None


def test_retrieval_uses_evidence_offsets_and_handles_missing_context():
    context=dict(document_key="d",source_spans=[[0,3],[3,6]])
    result=score(example(),"Python [S1]",[context],[{"source_id":1}])
    assert result["evidence_recall_at_k"]==1
    assert result["mrr"]==1
    assert result["citation_id_validity"]==1
    assert score(example(),"Python [S9]",[context],[{"source_id":1}])["citation_id_validity"]==0


def test_lexical_scores_do_not_confuse_short_words():
    assert not fact_present("yes","yesterday")
    assert overlap_f1("Python","Python [S1]")==1
