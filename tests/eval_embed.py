"""
임베딩 모델(+재랭킹)별 검색 평가 — 색인을 건드리지 않는 버전. 관리자 화면 [검색 평가 실행] 버튼이 이걸 서브프로세스로 돌린다.
(팀장 · 2026-09-11)

    python -m tests.eval_embed --backend local  --model intfloat/multilingual-e5-base
    python -m tests.eval_embed --backend remote --model BAAI/bge-m3 --url http://192.168.1.147:8002
    python -m tests.eval_embed --backend gemini
    python -m tests.eval_embed --backend local --model all-MiniLM-L6-v2 --rerank BAAI/bge-reranker-v2-m3 --topn 10

tests/eval_rag.py 와 다른 점:
  - data/chroma 의 활성 색인을 안 쓴다. 규칙 100개와 시험 문장을 이 자리에서 임베딩해 코사인으로 직접 순위를 매긴다
    (Chroma 도 코사인이라 결과는 같다). 그래서 .env 와 다른 모델을 골라도 서비스 색인은 그대로다.
  - 재랭킹(--rerank): 검색 상위 --topn 개를 GPU 서버 /rerank(backend/embed_server.py) 로 다시 줄 세운 뒤 채점.
  - hit@5 도 기록한다 (/fix 가 프롬프트에 넣는 후보 5개 안에 정답이 든 비율).
결과: data/rag_eval/retrieval_eval_<시각>[-rerank].json — eval_rag 와 같은 형식 + reranker·hit_at_5·evaluation_hash. 관리자 비교 표가 읽는다.
진행 출력: "[i/total]" 한 줄씩 (관리자 화면 진행률이 이 줄을 센다).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = ROOT / "data" / "rag_eval"
RERANKERS = ["BAAI/bge-reranker-v2-m3", "BAAI/bge-reranker-base", "cross-encoder/ms-marco-MiniLM-L-6-v2"]


def _cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def _retry(fn, what: str, sleep429: float = 20.0):
    """Gemini 분당 한도(429)면 잠시 쉬고 두 번 더. 그 밖의 오류는 그대로."""
    for attempt in range(3):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if "429" in str(e) and attempt < 2:
                print(f"  [{what}] 429 → {sleep429:.0f}초 대기", flush=True)
                time.sleep(sleep429)
                continue
            raise
    return None


def _rerank(url: str, model: str, query: str, cands: list[dict]) -> list[dict]:
    import urllib.request
    body = json.dumps({"query": query, "candidates": [c["text"] for c in cands], "model": model}).encode("utf-8")
    req = urllib.request.Request(f"{url.rstrip('/')}/rerank", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        scores = json.loads(r.read().decode("utf-8"))["scores"]
    ranked = sorted(zip(cands, scores), key=lambda x: -float(x[1]))
    return [{**c, "rerank_score": round(float(s), 4)} for c, s in ranked]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.environ.get("EMBEDDING_BACKEND", "gemini"), choices=["gemini", "local", "remote"])
    ap.add_argument("--model", default=None, help="local/remote 모델 이름 (gemini 는 고정)")
    ap.add_argument("--url", default=None, help="remote 임베딩·재랭킹 서버 (기본 .env 의 EMBEDDING_REMOTE_URL)")
    ap.add_argument("--rerank", default=None, help="재랭커 모델 이름. 없으면 검색만")
    ap.add_argument("--topn", type=int, default=10, help="재랭킹에 넣을 검색 상위 개수")
    ap.add_argument("--sleep", type=float, default=None, help="질의 사이 대기 초 (gemini 기본 0.8, 그 외 0)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    # backend/embedding.py 는 import 시점에 환경변수를 읽으므로, import 전에 덮어쓴다 (.env 파일은 안 바뀜)
    os.environ["EMBEDDING_BACKEND"] = args.backend
    if args.model:
        os.environ["EMBEDDING_LOCAL_MODEL" if args.backend == "local" else "EMBEDDING_REMOTE_MODEL"] = args.model
    if args.url:
        os.environ["EMBEDDING_REMOTE_URL"] = args.url
    from backend import embedding, golden, indexing                      # noqa: E402
    from backend.admin import eval_sheet_hash                             # noqa: E402

    rules = golden.rules()
    rows = golden.eval_set()
    if args.limit:
        rows = rows[: args.limit]
    sleep = args.sleep if args.sleep is not None else (0.8 if args.backend == "gemini" else 0.0)
    rerank_url = args.url or os.environ.get("EMBEDDING_REMOTE_URL", "http://192.168.1.147:8002")
    label = f"{embedding.EMBEDDING_MODEL}" + (f" + 재랭킹({args.rerank})" if args.rerank else "")
    print(f"[eval_embed] {args.backend}:{embedding.EMBEDDING_MODEL} · 규칙 {len(rules)} · 시험 문장 {len(rows)}" + (f" · 재랭킹 {args.rerank} (상위 {args.topn})" if args.rerank else ""), flush=True)

    # 1) 규칙 본문 임베딩 (색인이 쓰는 것과 같은 text 필드, 50개씩)
    doc_vecs: list[list[float]] = []
    for i in range(0, len(rules), 50):
        chunk = [r["text"] for r in rules[i:i + 50]]
        doc_vecs += _retry(lambda: embedding.embed_documents(chunk), "규칙 임베딩")
        if sleep:
            time.sleep(sleep)
    if len(doc_vecs) != len(rules):
        raise SystemExit(f"[eval_embed] 규칙 임베딩 수 불일치 {len(doc_vecs)} vs {len(rules)}")
    dim = len(doc_vecs[0])
    print(f"[eval_embed] 규칙 임베딩 완료 (dim {dim})", flush=True)

    # 2) 문장마다 질의 임베딩 → 코사인 순위 → (재랭킹) → 채점
    detail, fails = [], 0
    n_err = hit1 = hit3 = hit5 = normal_n = 0
    total = len(rows)
    for i, row in enumerate(rows, 1):
        text, expected = (row.get("text") or "").strip(), (row.get("expected_rule_id") or "").strip()
        is_normal = expected == "NONE"
        normal_n += int(is_normal)
        n_err += int(not is_normal)
        if i > 1 and sleep:
            time.sleep(sleep)
        try:
            q = _retry(lambda: embedding.embed_query(text), f"{i}/{total}")
            scored = sorted(((_cos(q, v), r) for v, r in zip(doc_vecs, rules)), key=lambda x: -x[0])
            cands = [{"id": r["id"], "type": r["type"], "text": r["text"], "unit": r.get("unit", ""), "score": round(s, 4)} for s, r in scored[: max(args.topn, 5)]]
            if args.rerank:
                cands = _rerank(rerank_url, args.rerank, text, cands[: args.topn])
            ids = [c["id"] for c in cands]
            h1, h3, h5 = (not is_normal) and ids[:1] == [expected], (not is_normal) and expected in ids[:3], (not is_normal) and expected in ids[:5]
            hit1 += int(h1); hit3 += int(h3); hit5 += int(h5)
            detail.append({"text": text, "expected_rule_id": expected, "is_normal": is_normal,
                           "candidates": [{k: c[k] for k in c if k != "text"} for c in cands[:5]],
                           "hit_at_1": h1, "hit_at_3": h3, "hit_at_5": h5, "error": None})
            mark = "-" if is_normal else ("O" if h3 else "X")
            print(f"[{i}/{total}] {mark} {expected:6} {text[:40]}", flush=True)
        except Exception as e:  # noqa: BLE001
            fails += int(not is_normal)
            detail.append({"text": text, "expected_rule_id": expected, "is_normal": is_normal, "candidates": [],
                           "hit_at_1": False, "hit_at_3": False, "hit_at_5": False, "error": f"{type(e).__name__}: {str(e)[:160]}"})
            print(f"[{i}/{total}] ! {expected:6} {text[:40]}  실패: {str(e)[:80]}", flush=True)

    r1, r3, r5 = (round(hit1 / n_err, 4), round(hit3 / n_err, 4), round(hit5 / n_err, 4)) if n_err else (None, None, None)
    print(f"[eval_embed] hit@1 {r1}  hit@3 {r3}  hit@5 {r5}  (오류 문장 {n_err} · 정상 {normal_n} · 실패 {fails})", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {
        "n": n_err, "total_n": len(rows), "normal_n": normal_n,
        "hit_at_1": r1, "hit_at_3": r3, "hit_at_5": r5,
        "threshold": None, "search_failures": fails, "k": 5,
        "index": {"active_collection": None, "provider": embedding.EMBEDDING_PROVIDER, "model": embedding.EMBEDDING_MODEL,
                  "dim": dim, "distance": "cosine", "text_version": indexing.TEXT_VERSION, "mode": "in-memory (tests/eval_embed.py)"},
        "reranker": args.rerank, "rerank_topn": args.topn if args.rerank else None,
        "data_hash": indexing._data_hash(rules),  # noqa: SLF001 — 색인과 같은 규칙 지문
        "evaluation_hash": eval_sheet_hash(),
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "runs": [{"label": label, "hit_at_1": r1, "hit_at_3": r3}],
        "rows": detail,
    }
    name = f"retrieval_eval_{stamp}{'-rerank' if args.rerank else ''}.json"
    (OUT_DIR / name).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[eval_embed] 저장: {name} (관리자 비교 표에 자동 표시)", flush=True)


if __name__ == "__main__":
    main()
