"""Versioned data; gold answers never enter the retrieval corpus."""
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    text: str = Field(min_length=1)
    source: str
    language: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    dataset: str
    language: str
    scenario: str
    group_id: str
    split: Literal["dev", "holdout"]
    question: str
    reference_answer: str
    expected_behavior: Literal["answer", "partial", "refuse", "clarify"]
    document_ids: list[str]
    evidence: list[Evidence] = []
    required_facts: list[str] = []
    forbidden_facts: list[str] = []
    history: list[Turn] = []
    annotation: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset(root: Path) -> tuple[dict[str, Document], list[Case]]:
    docs_list = [Document.model_validate(json.loads(line)) for line in
                 (root / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = [Case.model_validate(json.loads(line)) for line in
             (root / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    docs = {doc.id: doc for doc in docs_list}
    if len(docs) != len(docs_list) or len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate document or case ID")
    groups = {}
    for case in cases:
        if not set(case.document_ids) <= docs.keys():
            raise ValueError(f"{case.id}: missing corpus documents")
        if case.expected_behavior in {"answer", "partial"} and not case.evidence:
            raise ValueError(f"{case.id}: answerable case needs evidence")
        if case.group_id in groups and groups[case.group_id] != case.split:
            raise ValueError("Related cases must stay in the same split")
        groups[case.group_id] = case.split
        for evidence in case.evidence:
            if evidence.document_id not in case.document_ids:
                raise ValueError(f"{case.id}: evidence outside its corpus")
            if docs[evidence.document_id].text[evidence.start:evidence.end] != evidence.text:
                raise ValueError(f"{case.id}: invalid evidence offsets")
    manifest = root / "manifest.json"
    if manifest.exists():
        for name, expected in json.loads(manifest.read_text(encoding="utf-8")).get("files", {}).items():
            if Path(name).name != name or digest(root / name) != expected:
                raise ValueError(f"Dataset hash mismatch: {name}")
    return docs, cases
