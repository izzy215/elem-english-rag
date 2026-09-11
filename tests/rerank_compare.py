"""
재랭킹 비교 실험 — 검색 상위 N 을 GPU 서버의 크로스인코더(/rerank, backend/embed_server.py)로 다시 줄 세우면 hit@1·hit@3 이 오르나.
(팀장 · 2026-09-11. RAG 담당의 재랭킹 실험을 관리자 화면 표에 같이 놓기 위한 것)

    python -m tests.rerank_compare                    # eval.csv 전부, 검색 상위 10 → 재랭킹
    python -m tests.rerank_compare --step 4           # 4문장마다 하나 (약 115문장, 규칙 전체에 고르게) — 빠른 확인
    python -m tests.rerank_compare --topn 20 --sleep 0.8
    python -m tests.rerank_compare --url http://192.168.1.147:8002 --model BAAI/bge-reranker-v2-m3

동작: 문장마다 rag.search_rules(text, k=topn) (임베딩 검색, .env 의 EMBEDDING_BACKEND) → 후보 topn 개의 규칙 본문을 /rerank 에 보내
      점수순으로 재정렬 → "검색만" 과 "검색+재랭킹" 의 hit@1·hit@3 을 같은 문장으로 비교한다.
결과: data/rag_eval/rerank_compare_<시각>.json/.md 와, 관리자 화면 비교 표에 뜨도록 retrieval_eval_<시각>-rerank.json
      (eval_rag 와 같은 형식 + "reranker" 필드). 검색만의 결과는 이미 eval_rag 가 남기므로 따로 안 만든다.
비용: 문장 수만큼 임베딩 호출(gemini 면 분당 한도 → --sleep 기본 0.8초) + /rerank 호출(GPU, 빠름).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import golden, indexing, rag                             # noqa: E402

OUT_DIR = ROOT / "data" / "rag_eval"


def rerank(url: str, model: str, query: str, cands: list[dict], timeout: float = 30) -> list[dict]:
    body = json.dumps({"query": query, "candidates": [c["text"] for c in cands], "model": model}).encode("utf-8")
    req = urllib.request.Request(f"{url.rstrip('/')}/rerank", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    scores = out.get("scores") or out.get("results") or []
    if scores and isinstance(scores[0], dict):                        # [{index, score}] 형태도 받아 준다
        scores = [s.get("score", 0.0) for s in sorted(scores, key=lambda s: s.get("index", 0))]
    ranked = sorted(zip(cands, scores), key=lambda x: -float(x[1]))
    return [{**c, "rerank_score": round(float(s), 4)} for c, s in ranked]


def _search(text: str, k: int) -> list[dict]:
    """임베딩 검색. Gemini 분당 한도(429)면 20초 쉬고 두 번 더 시도 (eval_rag 로 462문장 돌릴 때 28% 가 429 였음)."""
    for attempt in range(3):
        try:
            return rag.search_rules(text, k=k)
        except Exception as e:  # noqa: BLE001
            if "429" in str(e) and attempt < 2:
                time.sleep(20)
                continue
            raise
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.1.147:8002")
    ap.add_argument("--model", default="BAAI/bge-reranker-v2-m3")
    ap.add_argument("--topn", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--step", type=int, default=1, help="n번째 문장마다 하나 (규칙 전체에 고르게 뽑아 빨리 볼 때: --step 4 ≈ 1/4)")
    ap.add_argument("--sleep", type=float, default=0.8)
    args = ap.parse_args()

    rows = [r for r in golden.eval_set() if (r.get("expected_rule_id") or "").strip() not in ("", "NONE")]
    if args.step > 1:
        rows = rows[:: args.step]
    if args.limit:
        rows = rows[: args.limit]
    manifest = indexing.load_manifest()
    print(f"[rerank] {len(rows)}문장 / 검색 상위 {args.topn} ({manifest.get('model')}) -> 재랭킹 {args.model} @ {args.url}", flush=True)

    detail, fails = [], 0
    for i, r in enumerate(rows, 1):
        text, expected = r["text"].strip(), r["expected_rule_id"].strip()
        if i > 1 and args.sleep:
            time.sleep(args.sleep)
        try:
            base = _search(text, args.topn)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  [{i:3}] 검색 실패: {str(e)[:60]}", flush=True)
            detail.append({"text": text, "expected_rule_id": expected, "error": str(e)[:120]})
            continue
        try:
            rr = rerank(args.url, args.model, text, base)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  [{i:3}] 재랭킹 실패: {str(e)[:60]}", flush=True)
            detail.append({"text": text, "expected_rule_id": expected, "error": f"rerank: {str(e)[:100]}"})
            continue
        b_ids, r_ids = [c["id"] for c in base], [c["id"] for c in rr]
        row = {"text": text, "expected_rule_id": expected, "is_normal": False,
               "base_top": b_ids[:3], "rerank_top": r_ids[:3],
               "base_hit1": bool(b_ids) and b_ids[0] == expected, "base_hit3": expected in b_ids[:3],
               "hit_at_1": bool(r_ids) and r_ids[0] == expected, "hit_at_3": expected in r_ids[:3],
               "in_topn": expected in b_ids,
               "candidates": [{"id": c["id"], "type": c["type"], "unit": c.get("unit"), "score": c.get("score"), "rerank_score": c["rerank_score"]} for c in rr[:3]],
               "error": None}
        detail.append(row)
        # 표시: O/X = 재랭킹 뒤 hit@3, 뒤 글자 = 검색만과 비교 (= 같음, + 재랭킹이 살림, - 재랭킹이 망침). 윈도 콘솔(cp949)이라 ASCII 만
        mark = ("O" if row["hit_at_3"] else "X") + ("=" if row["hit_at_3"] == row["base_hit3"] else ("+" if row["hit_at_3"] else "-"))
        print(f"  [{i:3}] {mark} {expected:6} {text[:40]:40} 검색 {b_ids[:3]} -> 재랭킹 {r_ids[:3]}", flush=True)

    ok = [d for d in detail if not d.get("error")]
    n = len(ok)
    m = lambda key: round(sum(1 for d in ok if d[key]) / n, 4) if n else None
    summary = {"n": n, "failures": fails, "topn": args.topn,
               "base": {"hit_at_1": m("base_hit1"), "hit_at_3": m("base_hit3")},
               "rerank": {"hit_at_1": m("hit_at_1"), "hit_at_3": m("hit_at_3")},
               "in_topn": m("in_topn")}
    print(f"\n[rerank] 검색만   hit@1 {summary['base']['hit_at_1']}  hit@3 {summary['base']['hit_at_3']}")
    print(f"[rerank] +재랭킹  hit@1 {summary['rerank']['hit_at_1']}  hit@3 {summary['rerank']['hit_at_3']}   (정답이 상위 {args.topn} 안에 있던 비율 {summary['in_topn']} = 재랭킹으로 닿을 수 있는 상한)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "reranker": args.model, "url": args.url, "index": manifest,
           "summary": summary, "rows": detail}
    (OUT_DIR / f"rerank_compare_{stamp}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # 관리자 비교 표용 (eval_rag 형식 + reranker)
    from backend.admin import eval_sheet_hash                          # 관리자 화면의 '같은 시험지' 판정과 같은 지문
    eval_hash = eval_sheet_hash()
    compat = {"n": n, "total_n": len(rows), "normal_n": 0, "hit_at_1": summary["rerank"]["hit_at_1"], "hit_at_3": summary["rerank"]["hit_at_3"],
              "threshold": None, "search_failures": fails, "k": 3, "index": {k: manifest.get(k) for k in ("active_collection", "provider", "model", "dim", "distance", "text_version")},
              "reranker": args.model, "rerank_topn": args.topn, "data_hash": manifest.get("data_hash"), "evaluation_hash": eval_hash,
              "evaluated_at": out["ran_at"], "runs": [{"label": f"{manifest.get('model')} + 재랭킹({args.model})", "hit_at_1": summary["rerank"]["hit_at_1"], "hit_at_3": summary["rerank"]["hit_at_3"]}],
              "rows": [{k: d.get(k) for k in ("text", "expected_rule_id", "is_normal", "candidates", "hit_at_1", "hit_at_3", "error")} for d in detail]}
    (OUT_DIR / f"retrieval_eval_{stamp}-rerank.json").write_text(json.dumps(compat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[rerank] 저장: rerank_compare_{stamp}.json, retrieval_eval_{stamp}-rerank.json (관리자 표에 자동 표시)")


if __name__ == "__main__":
    main()
