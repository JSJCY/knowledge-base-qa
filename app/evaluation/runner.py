"""Batch evaluation in isolated memory databases; never touches the application's KB."""
import argparse
import hashlib
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base
from app.evaluation.dataset import digest, load_dataset
from app.evaluation.metrics import score
from app.models.chat import Conversation, Message
from app.models.document import Chunk, Document
from app.services.chunking import split_text
from app.services.embedding import EmbeddingService, vec_to_bytes
from app.services.grounding import INSTRUCTIONS, check_claims
from app.services.llm import MockLLMService, get_llm_service
from app.services.rag import (
    SYSTEM_PROMPT_TEMPLATE,
    build_context,
    citation_dicts,
    complete_preparation,
    prepare_question,
)
from app.services.retrieval import RetrievedChunk


class HashEmbedding:
    """Offline plumbing fixture, never a real retrieval quality measurement."""
    def embed(self, texts):
        import numpy as np

        from app.evaluation.metrics import tokens
        result = []
        for text in texts:
            vector = np.zeros(128,dtype=np.float32)
            for token in tokens(text):
                vector[int(hashlib.sha256(token.encode()).hexdigest(),16)%128] += 1
            norm = np.linalg.norm(vector)
            result.append((vector/norm if norm else vector).tolist())
        return result


class RecordingLLM:
    def __init__(self, inner):
        self.inner, self.calls = inner, []
        self.mode = inner.mode

    def chat(self, messages):
        row = {"messages":messages}
        self.calls.append(row)
        answer = self.inner.chat(messages)
        row["output"] = answer
        return answer


def source_spans(text, chunk):
    return [[block.a,block.a+block.size] for block in
            SequenceMatcher(None,text,chunk,autojunk=False).get_matching_blocks() if block.size]


def mean_metrics(rows):
    names = {name for row in rows for name,value in row.get("scores",{}).items()
             if isinstance(value,(int,float)) and not isinstance(value,bool)}
    return {name:{"mean":sum(values)/len(values),"n":len(values)}
            for name in sorted(names)
            if (values := [row["scores"][name] for row in rows if isinstance(row.get("scores",{}).get(name),(int,float))])}


def write_summary(output, metadata, rows):
    groups = {}
    for field in ["dataset","language","split","scenario"]:
        groups[field] = {value:mean_metrics([r for r in rows if r[field] == value])
                         for value in sorted({r[field] for r in rows})}
    summary = dict(metadata=metadata, total=len(rows), errors=sum(r["status"] != "ok" for r in rows),
                   metrics=mean_metrics(rows), slices=groups,
                   failures=[r["id"] for r in rows if r["status"] != "ok" or r.get("scores",{}).get("forbidden_fact_count",0)>0
                             or r.get("scores",{}).get("behavior_match_heuristic",1)==0
                             or any(r.get("scores",{}).get(key) is not None and r["scores"][key]<1
                                    for key in ["semantic_correctness","completeness","faithfulness",
                                                "citation_support","behavior_match_judged","evidence_recall_at_k"])])
    times=sorted(r["latency_seconds"] for r in rows if "latency_seconds" in r)
    if times:
        summary["latency_seconds"]={"mean":sum(times)/len(times),"p50":times[len(times)//2],
                                    "p95":times[min(len(times)-1,int(len(times)*0.95))],"n":len(times)}
    (output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines = ["# RAG evaluation", "", f"- Task: {metadata['task']}",
             f"- Embedding: {metadata['embedding']}; LLM: {metadata['llm']}",
             f"- Cases: {len(rows)}; errors: {summary['errors']}",
             "- Lexical/behavior diagnostics are proxies, not answer accuracy.",
             "- null semantic metrics mean NOT EVALUATED; refusals do not earn full faithfulness.",
             "- Histories are supplied fixtures, not a generated conversation rollout.",
             "", "| Metric | Mean | Evaluated cases |", "|---|---:|---:|"]
    lines += [f"| {name} | {item['mean']:.4f} | {item['n']} |" for name,item in summary["metrics"].items()]
    lines += ["", "## Cases needing review", ""] + [f"- {case}" for case in summary["failures"]]
    (output/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return summary


def run(args):
    docs,cases = load_dataset(args.data)
    cases = [c for c in cases if (args.split == "all" or c.split == args.split)
             and (not args.dataset or c.dataset == args.dataset)]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise ValueError("No cases selected")
    args.output.mkdir(parents=True,exist_ok=False)
    settings = get_settings()
    if args.llm == "real" and args.task != "retrieval" and not settings.llm_enabled:
        raise ValueError("Real LLM requested but no API key configured")
    embedder = EmbeddingService(settings.embedding_model,settings.hf_endpoint) if args.embedding == "real" else HashEmbedding()
    llm = get_llm_service() if args.llm == "real" else MockLLMService()
    lock = threading.Lock()
    entries = {}
    selected_docs = {key for c in cases for key in c.document_ids}
    for key in sorted(selected_docs):
        chunks = split_text(docs[key].text,settings.chunk_size,settings.chunk_overlap)
        entries[key] = [(chunk,vec_to_bytes(vector),source_spans(docs[key].text,chunk))
                        for chunk,vector in zip(chunks,embedder.embed(chunks),strict=True)]
    class LockedEmbedding:
        def embed(self,texts):
            with lock:
                return embedder.embed(texts)
    try:
        commit = subprocess.check_output(["git","-c",f"safe.directory={Path.cwd().as_posix()}","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError,FileNotFoundError):
        commit = "unknown"
    metadata = dict(application_version=settings.version,schema_version=1, created_at=datetime.now(UTC).isoformat(),commit=commit,task=args.task,
                    embedding=args.embedding,embedding_model=settings.embedding_model if args.embedding=="real" else "hash-fixture",
                    llm=args.llm if args.task!="retrieval" else "none", model=settings.deepseek_model if args.llm=="real" else "mock",
                    corpus_sha256=digest(args.data/"corpus.jsonl"),cases_sha256=digest(args.data/"cases.jsonl"),
                    prompt_sha256=hashlib.sha256(SYSTEM_PROMPT_TEMPLATE.encode()).hexdigest(),
                    settings={name:getattr(settings,name) for name in ["chunk_size","chunk_overlap","llm_temperature",
                              "rag_min_relevance_score","rag_vector_weight","rag_keyword_weight","rag_candidate_multiplier",
                              "rag_history_limit","rag_history_char_budget","rag_query_rewrite_enabled",
                              "rag_grounded_output_enabled","rag_verify_claims_enabled","rag_keyword_idf_enabled"]},
                    top_k=args.top_k,split=args.split,workers=args.workers,
                    grounding_prompt_sha256=hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
                    verifier_sha256=hashlib.sha256(__import__("inspect").getsource(check_claims).encode()).hexdigest(),
                    runtime_files_sha256={str(p):digest(p) for p in sorted(Path("app").rglob("*.py"))},
                    retrieval_scope="XQuAD:20 selected paragraphs; HotpotQA:10 supplied distractor paragraphs; project:fixture scope")
    (args.output/"metadata.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")

    def one(case):
        started = time.perf_counter()
        row = dict(id=case.id,dataset=case.dataset,language=case.language,split=case.split,
                   scenario=case.scenario,case=case.model_dump(),status="ok")
        engine = create_engine("sqlite://")
        db = Session(engine)
        trace = RecordingLLM(llm)
        try:
            Base.metadata.create_all(engine)
            mappings = {}
            for key in case.document_ids:
                doc = Document(filename=docs[key].title+".txt",extension=".txt",status="indexed",chunk_count=len(entries[key]))
                db.add(doc)
                db.flush()
                for index,(text,vector,spans) in enumerate(entries[key]):
                    chunk = Chunk(document_id=doc.id,chunk_index=index,content=text,embedding=vector)
                    db.add(chunk)
                    db.flush()
                    mappings[chunk.id] = dict(chunk_id=chunk.id,document_id=doc.id,document_key=key,source_spans=spans,
                                              document_filename=doc.filename,chunk_index=index,content=text)
            db.commit()
            conv_id = None
            if case.history:
                conv = Conversation(title=case.question[:50])
                db.add(conv)
                db.flush()
                db.add_all([Message(conversation_id=conv.id,role=t.role,content=t.content) for t in case.history])
                db.commit()
                conv_id = conv.id
            kwargs = dict(question=case.question,top_k=args.top_k,conversation_id=conv_id,
                          history_limit=settings.rag_history_limit,history_char_budget=settings.rag_history_char_budget,
                          query_rewrite_enabled=settings.rag_query_rewrite_enabled,
                          candidate_multiplier=settings.rag_candidate_multiplier,
                          vector_weight=settings.rag_vector_weight,keyword_weight=settings.rag_keyword_weight,
                          keyword_idf=settings.rag_keyword_idf_enabled)
            preparation = prepare_question(db,LockedEmbedding(),llm=trace,**kwargs)
            retrieved = list(preparation.citations)
            row["retrieval_query"] = getattr(preparation,"retrieval_query",case.question)
            if args.task == "retrieval":
                answer,citations = "",[]
            elif args.task == "oracle":
                gold_ids = {key for key,info in mappings.items() if any(
                    info["document_key"] == e.document_id and any(a<e.end and b>e.start for a,b in info["source_spans"])
                    for e in case.evidence)}
                gold = [RetrievedChunk(db.get(Chunk,key),db.get(Document,mappings[key]["document_id"]),1.0) for key in sorted(gold_ids)]
                preparation.citations = gold
                preparation.messages[0]["content"] = SYSTEM_PROMPT_TEMPLATE.format(context=build_context(gold))
                answer = complete_preparation(preparation,trace,0)
                citations = citation_dicts(gold)
                retrieved = gold
            else:
                answer=complete_preparation(preparation,trace,settings.rag_min_relevance_score)
                citations=citation_dicts(preparation.citations)
            contexts = [{**mappings[r.chunk.id],"score":r.score} for r in retrieved]
            row.update(answer=answer,citations=citations,retrieved=contexts,llm_calls=trace.calls,quality=preparation.quality)
            row["scores"] = score(case,answer,contexts,citations)
            if args.task == "retrieval":
                row["scores"] = {k:v for k,v in row["scores"].items() if k in {
                    "evidence_recall_at_k","mrr","context_precision_at_k"}}
        except Exception as exc:
            row.update(status="error",error_type=type(exc).__name__,error=str(exc)[:500],llm_calls=trace.calls)
        finally:
            db.close()
            engine.dispose()
        row["latency_seconds"] = time.perf_counter()-started
        return row

    rows = []
    with (args.output/"cases.jsonl").open("w",encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for future in as_completed([pool.submit(one,c) for c in cases]):
                row = future.result()
                rows.append(row)
                handle.write(json.dumps(row,ensure_ascii=False)+"\n")
                handle.flush()
                print(f"{len(rows)}/{len(cases)} {row['id']} {row['status']}",flush=True)
    summary=write_summary(args.output,metadata,sorted(rows,key=lambda r:r["id"]))
    return 1 if summary["errors"] else 0


def compare(args):
    old,new = [json.loads((p/"summary.json").read_text(encoding="utf-8")) for p in [args.baseline,args.candidate]]
    for key in ["corpus_sha256","cases_sha256","task","split","embedding","llm"]:
        if old["metadata"][key] != new["metadata"][key]:
            raise ValueError(f"Incomparable runs: {key}")
    ids = [{json.loads(line)["id"] for line in (p/"cases.jsonl").read_text(encoding="utf-8").splitlines()}
           for p in [args.baseline,args.candidate]]
    if ids[0] != ids[1]:
        raise ValueError("Incomparable case sets")
    for key in ["judge_model","judge_rubric_sha256","metrics_sha256"]:
        if old["metadata"].get(key)!=new["metadata"].get(key):
            raise ValueError(f"Incomparable scoring protocol: {key}")
    deltas={k:new["metrics"][k]["mean"]-v["mean"] for k,v in old["metrics"].items()
            if k in new["metrics"] and v["n"]==new["metrics"][k]["n"]}
    report=dict(baseline=str(args.baseline),candidate=str(args.candidate),metric_deltas=deltas,
                errors_delta=new["errors"]-old["errors"],
                note="Positive deltas are not always improvements: forbidden_fact_count is lower-is-better.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    if args.fail_on_regression:
        for metric in args.metric:
            if metric not in deltas:
                raise ValueError(f"Cannot gate unevaluated or differently sized metric: {metric}")
        return int(report["errors_delta"]>0 or any(deltas[m] < -args.max_regression for m in args.metric))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest="command",required=True)
    run_parser=subs.add_parser("run")
    run_parser.add_argument("--data",type=Path,default=Path("evals/data"))
    run_parser.add_argument("--output",type=Path,required=True)
    run_parser.add_argument("--task",choices=["retrieval","e2e","oracle"],default="retrieval")
    run_parser.add_argument("--embedding",choices=["real","mock"],default="real")
    run_parser.add_argument("--llm",choices=["real","mock"],default="real")
    run_parser.add_argument("--dataset")
    run_parser.add_argument("--split",choices=["all","dev","holdout"],default="dev")
    run_parser.add_argument("--limit",type=int)
    run_parser.add_argument("--top-k",type=int,default=5)
    run_parser.add_argument("--workers",type=int,default=1)
    diff=subs.add_parser("compare")
    diff.add_argument("baseline",type=Path)
    diff.add_argument("candidate",type=Path)
    diff.add_argument("--output",type=Path,required=True)
    diff.add_argument("--fail-on-regression",action="store_true")
    diff.add_argument("--metric",action="append",default=[])
    diff.add_argument("--max-regression",type=float,default=0)
    judge_parser=subs.add_parser("judge")
    judge_parser.add_argument("input",type=Path)
    judge_parser.add_argument("--output",type=Path,required=True)
    judge_parser.add_argument("--model")
    judge_parser.add_argument("--retry-errors",action="store_true")
    judge_parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    if args.command=="judge":
        from app.evaluation.judge import judge_run
        if args.workers<1:
            parser.error("workers must be positive")
        return judge_run(args)
    if args.command=="compare" and args.max_regression<0:
        parser.error("max-regression cannot be negative")
    if args.command=="run" and (args.top_k<1 or args.workers<1 or (args.limit is not None and args.limit<1)):
        parser.error("top-k, workers and limit must be positive")
    return run(args) if args.command=="run" else compare(args)
