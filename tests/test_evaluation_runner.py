import json
from argparse import Namespace
from pathlib import Path

import pytest

from app.evaluation.runner import compare, run


def args(tmp_path):
    return Namespace(data=Path("evals/data"),output=tmp_path/"run",task="e2e",
                     embedding="mock",llm="mock",dataset="project",split="all",limit=2,
                     top_k=5,workers=1)


def test_offline_runner_saves_raw_outputs_and_no_semantic_quality_claim(tmp_path):
    options=args(tmp_path)
    assert run(options)==0
    rows=[json.loads(line) for line in (options.output/"cases.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows)==2
    assert all(row["scores"]["semantic_correctness"] is None for row in rows)
    assert all(row["llm_calls"] for row in rows)
    assert all(row["retrieved"] for row in rows)
    assert (options.output/"report.md").exists()


def test_comparison_rejects_mismatched_case_selection(tmp_path):
    options=args(tmp_path)
    run(options)
    candidate=tmp_path/"candidate"
    options.output=candidate
    options.limit=1
    run(options)
    with pytest.raises(ValueError,match="case sets"):
        compare(Namespace(baseline=tmp_path/"run",candidate=candidate,output=tmp_path/"diff.json",
                          fail_on_regression=False,metric=[],max_regression=0))


def test_gate_rejects_unevaluated_metrics(tmp_path):
    options=args(tmp_path)
    run(options)
    with pytest.raises(ValueError,match="unevaluated"):
        compare(Namespace(baseline=options.output,candidate=options.output,output=tmp_path/"diff.json",
                          fail_on_regression=True,metric=["semantic_correctness"],max_regression=0))
