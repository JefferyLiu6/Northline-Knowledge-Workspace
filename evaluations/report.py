"""Produce derived scores without rewriting model outputs in the raw run log."""
import json,re,statistics
from pathlib import Path

def build():
    root=Path(__file__).resolve().parent
    out=root/"results"
    latest={}
    for line in (out/"runs.jsonl").read_text().splitlines():
        row=json.loads(line)
        latest[row["case_id"],row["strategy"]]=row
    checks=json.loads((root/"fact_checks.json").read_text())
    corpus=json.loads((out/"corpus.json").read_text())
    chunks={c["id"]:c for c in corpus["chunks"]}
    documents={d["file_name"]:d["id"] for d in corpus["documents"]}
    cases={c["id"]:c for c in json.loads((root/"cases.json").read_text())}
    scored=[]
    for original in latest.values():
        row=dict(original)
        if not row.get("error"):
            # Accept both bracketed citations and explicit prose such as "Source 2".
            refs=set()
            for prose,number in re.findall(r"\bSource\s+(\d+)\b|\[(\d+)\]",row["answer"],re.I):
                refs.add(int(prose or number))
            row["citation_ids_valid"]=bool(refs) and all(1<=n<=len(row["retrieved_chunk_ids"]) for n in refs)
            row["citations_present"]=bool(refs)
            row["citation_scoring_version"]=2
            normalized = row["answer"].lower().replace(",", "").replace("**", "")
            patterns = checks.get(row["case_id"])
            expected_doc=documents.get(cases[row["case_id"]]["source_file"])
            row["source_document_hit"] = any(chunks[c]["document_id"] == expected_doc for c in row["retrieved_chunk_ids"]) if expected_doc else None
            evidence = "\n".join(chunks[c]["content"] for c in row["retrieved_chunk_ids"]).lower().replace(",", "").replace("**", "")
            evidence3 = "\n".join(chunks[c]["content"] for c in row["retrieved_chunk_ids"][:3]).lower().replace(",", "").replace("**", "")
            row["critical_evidence_top3"] = all(re.search(p, evidence3, re.I) for p in patterns) if patterns else None
            row["critical_evidence_present"] = all(re.search(p, evidence, re.I) for p in patterns) if patterns else None
            row["critical_facts_pass"] = all(re.search(p, normalized, re.I) for p in patterns) if patterns else None
            row["explicit_refusal"] = bool(re.search(r"^no relevant (?:content|information)", normalized.strip()))

        scored.append(row)
    (out/"scored.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in scored))
    summary={}
    for mode in ["vector","hybrid","hybrid_rerank"]:
        all_rows=[r for r in scored if r["strategy"]==mode]
        good=[r for r in all_rows if not r.get("error")]
        pos=[r for r in good if r["category"]!="unanswerable"]
        neg=[r for r in good if r["category"]=="unanswerable"]
        def avg(rows,fn):return statistics.mean(fn(r) for r in rows) if rows else None
        fact_rows=[r for r in good if r["critical_facts_pass"] is not None]
        summary[mode]=dict(completed=len(good),errors=len(all_rows)-len(good),
            source_document_recall_at_5=avg(pos,lambda r:r["source_document_hit"]),
            critical_evidence_coverage=avg(fact_rows,lambda r:r["critical_evidence_present"]),
            critical_evidence_top3=avg(fact_rows,lambda r:r["critical_evidence_top3"]),
            critical_fact_cases=len(fact_rows),
            critical_fact_pass_rate=avg(fact_rows,lambda r:r["critical_facts_pass"]),
            answerable_explicit_refusal_rate=avg(pos,lambda r:r["explicit_refusal"]),
            judge_correct_but_fact_check_failed=sum(r["judge"]["correct"] and not r["critical_facts_pass"] for r in fact_rows),
            recall_at_5=avg(pos,lambda r:r["recall_at_5"]),
            hit_at_5=avg(pos,lambda r:r["hit_at_5"]),
            judge_answer_correct=avg(good,lambda r:r["judge"]["correct"]),
            judge_unsupported_rate=avg(good,lambda r:r["judge"]["unsupported"]),
            judge_citation_correct=avg(pos,lambda r:r["citation_ids_valid"] and r["judge"]["citations_supported"]),
            unanswerable_explicit_refusal_rate=avg(neg,lambda r:r["explicit_refusal"]),
            unanswerable_abstention=avg(neg,lambda r:r["judge"]["abstained"]),
            median_retrieval_seconds=statistics.median(r["retrieval_seconds"] for r in good) if good else None,
            median_answer_seconds=statistics.median(r["answer_seconds"] for r in good) if good else None)
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    return summary,scored

if __name__=="__main__":
    print(json.dumps(build()[0],indent=2))
