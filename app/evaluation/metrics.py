"""Deterministic diagnostics. Lexical overlap is NOT semantic accuracy."""
import re
from collections import Counter

REFUSAL = re.compile(r"未找到|未提供|资料不足|无法可靠|没有.*(?:资料|信息)|cannot (?:answer|reliably)|not (?:enough|provided)|insufficient", re.I)
CLARIFY = re.compile(r"请(?:说明|明确| уточ)|哪个|哪种|clarify|which (?:product|limit)", re.I)
CITE = re.compile(r"\[S(\d+)\]")


def tokens(text):
    text = CITE.sub("", text).lower()
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text)


def fact_present(fact, answer):
    if re.fullmatch(r"[a-zA-Z0-9 _.:/-]+", fact):
        return re.search(r"(?<!\w)" + re.escape(fact.strip()) + r"(?!\w)", answer, re.I) is not None
    return "".join(tokens(fact)) in "".join(tokens(answer))


def overlap_f1(reference, answer):
    ref, pred = Counter(tokens(reference)), Counter(tokens(answer))
    overlap = sum((ref & pred).values())
    if not overlap:
        return 0.0
    precision, recall = overlap/sum(pred.values()), overlap/sum(ref.values())
    return 2*precision*recall/(precision+recall)


def covered(evidence, contexts):
    ranges = [span for c in contexts if c["document_key"] == evidence.document_id for span in c["source_spans"]]
    return all(char.isspace() or any(start <= i < end for start,end in ranges)
               for i,char in enumerate(evidence.text, evidence.start))


def relevant(evidence, context):
    return context["document_key"] == evidence.document_id and any(
        start < evidence.end and end > evidence.start for start,end in context["source_spans"])


def score(case, answer, contexts, citations):
    evidence = case.evidence
    relevant_ranks = [i+1 for i,c in enumerate(contexts) if any(relevant(e,c) for e in evidence)]
    hits = [fact_present(f, answer) for f in case.required_facts]
    forbidden = [f for f in case.forbidden_facts if fact_present(f,answer)]
    has_facts = any(hits)
    behavior = ("partial" if has_facts else "refuse") if REFUSAL.search(answer) else (
        "clarify" if CLARIFY.search(answer) and not has_facts else "answer")
    return {
        "evidence_recall_at_k": sum(covered(e,contexts) for e in evidence)/len(evidence) if evidence else None,
        "mrr": 1/relevant_ranks[0] if relevant_ranks else (0.0 if evidence else None),
        "context_precision_at_k": len(relevant_ranks)/len(contexts) if evidence and contexts else (0.0 if evidence else None),
        "answer_token_f1": overlap_f1(case.reference_answer,answer) if case.expected_behavior in {"answer","partial"} else None,
        "required_fact_coverage": sum(hits)/len(hits) if hits else None,
        "forbidden_fact_count": len(forbidden),
        "forbidden_facts_found": forbidden,
        "detected_behavior": behavior,
        "behavior_match_heuristic": float(behavior == case.expected_behavior),
        "citation_id_validity": sum(1 for n in CITE.findall(answer) if int(n) in {
            c.get("source_id",i+1) for i,c in enumerate(citations)})/len(CITE.findall(answer)) if CITE.findall(answer) else None,
        "semantic_correctness": None,
        "faithfulness": None,
        "citation_support": None,
    }
