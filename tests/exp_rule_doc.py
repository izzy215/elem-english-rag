"""규칙 색인 문서 구성 실험 (RAG 팀원 실험 1번을 코드 수정 없이 재 본다).
고정: e5-base(강의실 8002), 시험지 eval.csv 오류 300문장, 데이터 d7877da. 바꾸는 것: 규칙 문서에 무엇을 넣나.
지표: 규칙 설명문 검색만의 hit@1/3/5, 그리고 틀린 예문 검색과 합친(merge_candidates) hit@1/3/5 (/fix 가 실제로 쓰는 것)."""
import os, sys, csv, json, math, time
os.chdir(r"D:\2026project\NIPA-Google Study Jam PBL\project")
sys.path.insert(0, ".")
from backend import golden, embedding, textbook

rules = golden.rules()
evals = [r for r in csv.DictReader(open("data/golden/eval.csv", encoding="utf-8")) if r["expected_rule_id"] not in ("", "NONE")]
print(f"규칙 {len(rules)} · 시험 문장 {len(evals)} · 임베딩 {embedding.EMBEDDING_PROVIDER} {embedding.EMBEDDING_MODEL}")

def term(t):  # "과거시제(시간)" → "과거시제"
    import re
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", t or "")).strip()

VARIANTS = {
    "A text (지금)":            lambda r: r["text"],
    "B type+short+text":       lambda r: f"{r['type']}. {r.get('short','')}. {r['text']}",
    "C type+text":             lambda r: f"{r['type']}. {r['text']}",
    "D short+text":            lambda r: f"{r.get('short','')}. {r['text']}",
    "E type+short+text+wrong": lambda r: f"{r['type']}. {r.get('short','')}. {r['text']} 틀린 예: {r.get('wrong_example','')}",
}

t0 = time.time()
qvecs = [embedding.embed_query(e["text"]) for e in evals]
print(f"질의 임베딩 {len(qvecs)}개 {time.time()-t0:.1f}s")

def cos(a, b):
    return sum(x*y for x, y in zip(a, b))   # 둘 다 정규화돼 있어 내적 = 코사인

# 예문 검색 결과는 문서 구성과 무관하니 한 번만
ex_by_q = [textbook.search_examples(e["text"], k=5, qvec=q) for e, q in zip(evals, qvecs)]

def hits(rank_lists):
    n = len(rank_lists)
    return tuple(round(100*sum(1 for e, ids in zip(evals, rank_lists) if e["expected_rule_id"] in ids[:k])/n, 1) for k in (1, 3, 5))

print(f"\n{'문서 구성':<26} {'설명문만 h@1/3/5':>20}   {'합침(예문+설명문) h@1/3/5':>26}")
for name, fn in VARIANTS.items():
    docs = [fn(r) for r in rules]
    dvecs = embedding.embed_documents(docs)
    ranked = []
    merged = []
    for q, ex in zip(qvecs, ex_by_q):
        scored = sorted(((cos(q, d), r["id"]) for d, r in zip(dvecs, rules)), reverse=True)
        ids = [rid for _, rid in scored]
        ranked.append(ids)
        by_rules = [{"id": rid, "score": s, "type": "", "text": ""} for s, rid in scored[:5]]
        merged.append([c["id"] for c in textbook.merge_candidates(ex, by_rules, k=5)])
    a = hits(ranked); b = hits(merged)
    print(f"{name:<26} {a[0]:>5} / {a[1]:>5} / {a[2]:>5}   {b[0]:>8} / {b[1]:>5} / {b[2]:>5}")
print("\n(참고) 예문 검색만:", hits([[c["id"] for c in ex] for ex in ex_by_q]))
