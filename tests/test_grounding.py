import json

import pytest

from app.models.document import Chunk, Document
from app.services.grounding import generate_grounded
from app.services.retrieval import RetrievedChunk


class Replies:
    mode="fake"
    def __init__(self,*replies):
        self.replies=iter(replies)
    def chat(self,messages):
        return next(self.replies)


def source():
    return RetrievedChunk(Chunk(id=4,chunk_index=0,content="FastAPI uses Python."),Document(id=2,filename="kb.txt"),0.9)


def answer(text="FastAPI uses Python.",quote="FastAPI uses Python.",source_id=1):
    return json.dumps({"behavior":"answer","claims":[{"text":text,"evidence":[{"source_id":source_id,"quote":quote}]}]})


def messages():
    return [{"role":"system","content":"sources"},{"role":"user","content":"Language?"}]


def test_valid_claim_has_only_used_citation():
    output=generate_grounded(Replies(answer()),messages(),[source(),source()],verify=False)
    assert output.answer=="FastAPI uses Python. [S1]"
    assert len(output.citations)==1


@pytest.mark.parametrize("raw",[answer(source_id=9),answer(quote="invented quote"),"not JSON",
                               '{"behavior":"answer","claims":[]}'])
def test_invalid_citations_and_malformed_output_fail_closed(raw):
    output=generate_grounded(Replies(raw),messages(),[source()],verify=False)
    assert output.quality["status"]=="rejected"
    assert output.citations==[]


def test_semantic_verifier_rejects_contradictory_claim_even_with_real_quote():
    output=generate_grounded(Replies(answer(text="FastAPI uses Java."),
        '{"assessments":[{"index":0,"supported":false,"reason":"Python contradicts Java"}]}'),
        messages(),[source()])
    assert output.quality["status"]=="rejected"
    assert "Java" not in output.answer


def test_incomplete_verification_cannot_pass():
    output=generate_grounded(Replies(answer(),'{"assessments":[]}'),messages(),[source()])
    assert output.quality["status"]=="rejected"


def test_refusal_has_no_claims_and_no_faithfulness_score():
    output=generate_grounded(Replies('{"behavior":"refuse","message":"Insufficient evidence","claims":[]}'),
                             messages(),[source()])
    assert output.quality["status"]=="not_applicable"
    assert output.citations==[]
