"""/ask "맞는 문장이에요?" 판정 실험 (2026-09-16, 팀장) — ask.py 는 안 건드리고 그 프롬프트를 읽어만 온다.

  A. 지금 방식: CORRECTNESS_PROMPT 에 규칙 100개 통째
  B. 검색만 빌리기: 같은 프롬프트에 /fix 와 같은 후보 8개 (규칙 설명문 색인 + 틀린 예문 색인 번갈아 합침, 닮은 실수 줄 포함)
  C. 팀원 구현 그대로 (ask._correctness_candidate_rules, 커밋 1689dc8): 후보 8 + ALL 규칙 10, 닮은 실수 줄 없음
검증기·재확인·되살리기는 둘 다 없음 (ask 의 자체 판정 그대로). 채점은 eval_fix 와 같이 쌍둥이 규칙 인정.

    python -m tests.exp_ask_check --backend local --per-rule 1        # 규칙당 1문장 + 정상 60 (약 160문장 × 2)
    python -m tests.exp_ask_check --backend local                     # 360문장 × 2
결과: data/rag_eval/ask_check_<시각>.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import ask, embedding, golden, llm, textbook, tutor          # noqa: E402
from backend.rag import search_rules                                       # noqa: E402
from tests.eval_fix import load_eval                                       # noqa: E402

OUT_DIR = ROOT / "data" / "rag_eval"
TOP_K = tutor.RAG_TOP_K


def rules_block_all() -> str:
    return "\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in golden.rules())


def rules_block_search(text: str) -> tuple[str, list[str]]:
    """/fix 와 같은 후보 8개 (tutor.diagnose 의 후보 만들기와 같은 함수·같은 k). 유닛·공통 규칙 보충은 안 함 (ask 는 유닛을 모를 수 있음)."""
    qvec = embedding.embed_query(text)
    cands = search_rules(text, k=TOP_K)
    ex = textbook.search_examples(text, k=TOP_K * 2, qvec=qvec)
    top = textbook.merge_candidates(ex[:TOP_K], cands[:TOP_K], k=TOP_K) if ex else [{**c, "from": "rules"} for c in cands[:TOP_K]]
    ex_by_rule = {c["id"]: c for c in ex}
    for c in top:
        if not c.get("example") and c["id"] in ex_by_rule:
            e = ex_by_rule[c["id"]]
            c.update({"example": e.get("example"), "fix": e.get("fix", ""), "correct": e.get("correct", "")})
    return tutor._rules_block(top), [c["id"] for c in top]


def judge(row: dict, out: dict) -> str:
    ok = bool(out.get("ok", True)); rid = out.get("rule_id")
    if row["is_normal"]:
        return "✓ 정상 유지" if ok else f"✗ 오교정 {rid}"
    if ok:
        return "✗ 맞는 문장이라 함"
    exp = row["expected_rule_id"]
    if rid == exp:
        return "✓"
    if rid in set(textbook.rule_family(exp)):
        return f"✓≈ {rid}"
    return f"✗ {rid}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None)
    ap.add_argument("--per-rule", type=int, default=0, help="규칙당 앞 n 문장만 (0 = 전부)")
    ap.add_argument("--normal", type=int, default=-1, help="정상 문장 앞 n개 (-1 = 전부)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0)
    ap.add_argument("--conds", default="AB", help="돌릴 조건 (예: AB, C, ABC)")
    args = ap.parse_args()

    rows = load_eval()
    if args.per_rule:
        seen: dict[str, int] = {}
        keep = []
        for r in rows:
            if r["is_normal"]:
                keep.append(r); continue
            n = seen.get(r["expected_rule_id"], 0)
            if n < args.per_rule:
                keep.append(r); seen[r["expected_rule_id"]] = n + 1
        rows = keep
    if args.normal >= 0:
        normals = [r for r in rows if r["is_normal"]][: args.normal]
        rows = [r for r in rows if not r["is_normal"]] + normals
    if args.limit:
        rows = rows[: args.limit]
    all_block = rules_block_all()
    conds = [c for c in args.conds.upper() if c in "ABC"]
    print(f"[exp_ask_check] {len(rows)}문장 × {conds} (A 규칙 100 / B 검색 후보 {TOP_K}+닮은 실수 / C 팀원 구현) · backend={args.backend or llm.settings.llm_backend}", flush=True)

    results = []
    t_all = time.time()
    for i, row in enumerate(rows, 1):
        text = row["text"]
        q = f"{text} 이거 맞아?"
        rec = {"text": text, "expected": row["expected_rule_id"], "is_normal": row["is_normal"], "by": {}}
        for cond in conds:
            t0 = time.time()
            try:
                if cond == "A":
                    block, ids = all_block, None
                elif cond == "B":
                    block, ids = rules_block_search(text)
                else:                                                      # C: ask.py 의 함수·형식 그대로
                    eng = " ".join(__import__("re").findall(r"[A-Za-z][A-Za-z']*", q)) or q
                    rules = ask._correctness_candidate_rules(eng) or golden.rules()
                    block, ids = "\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in rules), [r["id"] for r in rules]
                prompt = ask.CORRECTNESS_PROMPT.format(grade="4학년", rules_block=block, question=q)
                out = llm.generate_json(prompt, backend=args.backend, fallback=False)
                out.pop("_llm", None)
                j = judge(row, out)
                rec["by"][cond] = {"ok": out.get("ok"), "rule_id": out.get("rule_id"), "fixed": out.get("fixed"), "judge": j,
                                   "ms": int((time.time() - t0) * 1000), "cands": ids, "error": None}
            except Exception as e:  # noqa: BLE001
                rec["by"][cond] = {"ok": None, "rule_id": None, "fixed": None, "judge": "! 실패", "ms": int((time.time() - t0) * 1000), "cands": None, "error": str(e)[:200]}
            if args.sleep:
                time.sleep(args.sleep)
        results.append(rec)
        print(f"  [{i:3}/{len(rows)}] " + " ".join(f"{c} {rec['by'][c]['judge']:14}" for c in conds) + f" {text!r}", flush=True)

    def score(cond: str) -> dict:
        err = [r for r in results if not r["is_normal"]]; nor = [r for r in results if r["is_normal"]]
        return {"rule_hit": sum(r["by"][cond]["judge"].startswith("✓") for r in err), "err_n": len(err),
                "normal_kept": sum(r["by"][cond]["judge"].startswith("✓") for r in nor), "normal_n": len(nor),
                "avg_ms": int(sum(r["by"][cond]["ms"] for r in results) / max(1, len(results)))}
    summary = {c: score(c) for c in conds}
    for c, s in summary.items():
        print(f"[exp_ask_check] {c}: 규칙 정답 {s['rule_hit']}/{s['err_n']} = {s['rule_hit'] / max(1, s['err_n']) * 100:.1f}%  정상 유지 {s['normal_kept']}/{s['normal_n']}  평균 {s['avg_ms']}ms", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"ask_check_{datetime.now():%Y%m%d-%H%M}.json"
    out_path.write_text(json.dumps({"ran_at": datetime.now().isoformat(timespec="seconds"), "backend": args.backend or llm.settings.llm_backend,
                                    "n": len(rows), "top_k": TOP_K, "summary": summary, "results": results, "elapsed_s": int(time.time() - t_all)},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {out_path}", flush=True)


if __name__ == "__main__":
    main()
