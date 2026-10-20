"""Build the checked-in subset from explicitly supplied raw source files."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from app.evaluation.dataset import digest, load_dataset

SEED = 20261020


def stable_id(prefix, text):
    return prefix + hashlib.sha256(text.encode()).hexdigest()[:16]


def build(xquad: Path, hotpot: Path, output: Path):
    rng = random.Random(SEED)
    docs, cases = {}, []
    def add_doc(prefix, title, text, source, language):
        doc_id = stable_id(prefix, title + "\n" + text)
        docs[doc_id] = dict(id=doc_id, title=title, text=text, source=source, language=language)
        return doc_id

    paragraphs = [(article["title"], para) for article in json.loads(xquad.read_text(encoding="utf-8"))["data"]
                  for para in article["paragraphs"]]
    for title, para in rng.sample(paragraphs, 20):
        qa = rng.choice(para["qas"])
        doc_id = add_doc("xq-", title, para["context"], "XQuAD zh", "zh")
        answer = qa["answers"][0]
        start = answer["answer_start"]
        cases.append(dict(id="xquad-" + qa["id"], dataset="xquad_zh", language="zh",
                          scenario="answerable", group_id=doc_id, question=qa["question"],
                          reference_answer=answer["text"], expected_behavior="answer",
                          document_ids=[doc_id], required_facts=[answer["text"]],
                          evidence=[dict(document_id=doc_id, start=start, end=start+len(answer["text"]),
                                         text=answer["text"])], annotation="inherited_original_span"))
    raw = json.loads(hotpot.read_text(encoding="utf-8"))
    rows = [x["row"] for x in raw["rows"]] if isinstance(raw, dict) else raw
    for row in rng.sample(rows, 20):
        context = row["context"]
        pairs = list(zip(context["title"], context["sentences"], strict=True)) if isinstance(context, dict) else context
        ids, spans = {}, {}
        for title, sentences in pairs:
            text = "".join(sentences)
            doc_id = add_doc("hp-", title, text, "HotpotQA distractor validation", "en")
            ids[title] = doc_id
            offset = 0
            for index, sentence in enumerate(sentences):
                spans[(title,index)] = dict(document_id=doc_id, start=offset,
                                           end=offset+len(sentence), text=sentence)
                offset += len(sentence)
        facts = row["supporting_facts"]
        supports = list(zip(facts["title"], facts["sent_id"], strict=True)) if isinstance(facts, dict) else facts
        row_id = row.get("id", row.get("_id"))
        cases.append(dict(id="hotpot-" + row_id, dataset="hotpotqa", language="en",
                          scenario="multihop_distractors", group_id="hotpot-" + row_id,
                          question=row["question"], reference_answer=row["answer"], expected_behavior="answer",
                          document_ids=list(ids.values()), evidence=[spans[tuple(pair)] for pair in supports],
                          required_facts=[row["answer"]], annotation="inherited_supporting_facts"))
    authored = json.loads((output / "project_cases.source.json").read_text(encoding="utf-8"))
    docs.update({doc["id"]: doc for doc in authored["documents"]})
    cases.extend(authored["cases"])
    for case in cases:
        case["split"] = "holdout" if int(hashlib.sha256(case["group_id"].encode()).hexdigest()[:8],16) % 4 == 0 else "dev"
    xquad_ids = [key for key in docs if key.startswith("xq-")]
    for case in cases:
        if case["dataset"] == "xquad_zh":
            case["document_ids"] = xquad_ids
    output.mkdir(parents=True, exist_ok=True)
    for name, values in [("corpus.jsonl", list(docs.values())), ("cases.jsonl", cases)]:
        (output / name).write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in values),encoding="utf-8",newline="\n")
    manifest = dict(schema_version=1, dataset_version="1.0.0", seed=SEED, count=len(cases),
                    sources=[dict(name="XQuAD zh", url="https://raw.githubusercontent.com/google-deepmind/xquad/master/xquad.zh.json",
                                  sha256=digest(xquad), license="CC-BY-SA-4.0"),
                             dict(name="HotpotQA validation first 100 rows", url="https://datasets-server.huggingface.co/rows?dataset=hotpotqa%2Fhotpot_qa&config=distractor&split=validation&offset=0&length=100",
                                  sha256=digest(hotpot), license="CC-BY-SA-4.0",
                                  kaggle="https://www.kaggle.com/datasets/jeromeblanchet/hotpotqa-question-answering-dataset")],
                    files={name:digest(output/name) for name in ["corpus.jsonl","cases.jsonl","project_cases.source.json"]})
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8",newline="\n")
    load_dataset(output)
    print(f"Validated {len(cases)} cases and {len(docs)} documents")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xquad",type=Path,required=True)
    parser.add_argument("--hotpot",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("evals/data"))
    args=parser.parse_args()
    build(args.xquad,args.hotpot,args.output)
