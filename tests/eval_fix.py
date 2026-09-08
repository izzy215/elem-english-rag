"""
/fix 비교 실험 — eval.csv 문장을 같은 프롬프트·같은 규칙 조각으로 Gemini / 로컬 모델에 보내 표로 만든다.
(docs/plan-B/local-llm-plan.md 작업 4)

실행 (project 폴더에서, 가상환경 활성화 후):
    python -m tests.eval_fix                       # .env 의 LLM_BACKEND 하나만
    python -m tests.eval_fix --backend gemini
    python -m tests.eval_fix --backend local
    python -m tests.eval_fix --backend claude
    python -m tests.eval_fix --backend all         # 설정된 백엔드 전부 (gemini, claude, .env 의 LLM_ENDPOINTS 이름들)
    python -m tests.eval_fix --backend gemini,claude,groq,teacher   # 콤마로 직접 고르기
    python -m tests.eval_fix --backend both --limit 3   # 앞 3문장만 (연습용)

결과:
    data/rag_eval/fix_compare.json   문장별 원본 응답 (git 제외)
    화면에 마크다운 표 → 발표 자료에 붙이면 됨

오답노트·문장 로그에는 기록하지 않는다 (tutor.fix() 를 안 부르고 프롬프트 조립 + llm 호출만 한다).
비용: 문장 수 × 백엔드 수 만큼 LLM 호출. 무료 등급이면 한도 주의.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import llm, tutor                                    # noqa: E402
from backend.config import settings                               # noqa: E402

OUT_DIR = ROOT / "data" / "rag_eval"


def load_eval() -> list[dict]:
    path = tutor._golden_path("eval.csv")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["expected_rule_id"] = (r.get("expected_rule_id") or "").strip()
        r["is_normal"] = r["expected_rule_id"] in ("", "NONE")
    return rows


def build_prompt(text: str, rules: list[dict], level: int = 2, unit: str = "U3") -> str:
    """tutor.fix() 와 똑같은 폴백 프롬프트 (규칙 전부). RAG 가 붙으면 candidates 를 검색 결과로 바꿔 'rag' 조건도 비교할 수 있다."""
    unit_row = tutor.unit_info(level, unit)
    return tutor._render(
        tutor.PROMPT_FILE.read_text(encoding="utf-8"),
        mission=unit_row.get("mission") or "(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words=", ".join((unit_row.get("hint_words") or "").split(";")) or "(없음)",
        all_rules=tutor._rules_block(rules),
        sentence=text,
    )


def run_one(text: str, backend: str, rules: list[dict]) -> dict:
    prompt = build_prompt(text, rules)
    t0 = time.time()
    try:
        out = llm.generate_json(prompt, backend=backend)
        info = out.pop("_llm", {})
        rule_id = None if out.get("ok") else out.get("rule_id")
        if rule_id and not tutor.find_rule(rule_id):
            rule_id = f"?{rule_id}"                                # 목록에 없는 id 를 지어냄
        return {"backend": backend, "model": info.get("model"), "ms": info.get("ms", int((time.time() - t0) * 1000)),
                "ok": bool(out.get("ok")), "rule_id": rule_id, "fixed": out.get("fixed"), "full_fixed": out.get("full_fixed"),
                "more_errors": out.get("more_errors"), "error": None, "fallback_from": info.get("fallback_from")}
    except llm.LLMError as e:
        return {"backend": backend, "model": None, "ms": int((time.time() - t0) * 1000), "ok": None, "rule_id": None,
                "fixed": None, "full_fixed": None, "more_errors": None, "error": str(e)[:200], "fallback_from": None}


def judge(row: dict, res: dict) -> str:
    """✓ 정답 규칙 / ✓ 정상 유지 / ✗ 오교정(정상 문장을 고침) / ✗ 다른 규칙 / ! 실패"""
    if res["error"]:
        return "! 실패"
    if row["is_normal"]:
        return "✓ 정상 유지" if res["ok"] else f"✗ 오교정 {res['rule_id']}"
    if res["ok"]:
        return "✗ 놓침 (ok)"
    return "✓" if res["rule_id"] == row["expected_rule_id"] else f"✗ {res['rule_id']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None, help="gemini | claude | local | both(gemini+local) | all | 콤마 목록 (기본: .env 의 LLM_BACKEND)")
    ap.add_argument("--limit", type=int, default=0, help="앞 n 문장만")
    ap.add_argument("--out", default=str(OUT_DIR / "fix_compare.json"))
    args = ap.parse_args()

    b = (args.backend or settings.llm_backend or "gemini").lower()
    backends = llm.backends() if b == "all" else [x.strip() for x in b.split(",") if x.strip()]
    rows = load_eval()
    if args.limit:
        rows = rows[: args.limit]
    rules = tutor.rules()
    print(f"eval {len(rows)}문장 × {backends} · 규칙 {len(rules)}개 · 모델 " + ", ".join(f"{b}={llm._model_of(b)}" for b in backends), flush=True)

    results = []
    for i, row in enumerate(rows, 1):
        entry = {"text": row["text"], "expected": row["expected_rule_id"], "is_normal": row["is_normal"], "note": row.get("note", ""), "by": {}}
        for b in backends:
            res = run_one(row["text"], b, rules)
            res["judge"] = judge(row, res)
            entry["by"][b] = res
            print(f"  [{i:2}/{len(rows)}] {b:6} {res['judge']:12} {res['ms']:>6}ms  {row['text']!r}" + (f"  ← {res['error']}" if res["error"] else ""), flush=True)
        results.append(entry)

    # 합계
    summary = {}
    for b in backends:
        n_err = sum(1 for e in results if not e["is_normal"])
        n_norm = sum(1 for e in results if e["is_normal"])
        hit = sum(1 for e in results if not e["is_normal"] and e["by"][b]["judge"] == "✓")
        keep = sum(1 for e in results if e["is_normal"] and e["by"][b]["judge"].startswith("✓"))
        fail = sum(1 for e in results if e["by"][b]["error"])
        ms = [e["by"][b]["ms"] for e in results if not e["by"][b]["error"]]
        summary[b] = {"rule_hit": f"{hit}/{n_err}", "normal_kept": f"{keep}/{n_norm}", "failures": fail,
                      "avg_ms": int(sum(ms) / len(ms)) if ms else None, "model": next((e["by"][b]["model"] for e in results if e["by"][b]["model"]), None)}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "prompt_file": tutor.PROMPT_FILE.name, "rules_n": len(rules),
           "backends": backends, "summary": summary, "results": results}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 마크다운 표
    head = "| 문장 | 정답 | " + " | ".join(f"{b} ({summary[b]['model']})" for b in backends) + " |"
    print("\n" + head)
    print("|---|---|" + "---|" * len(backends))
    for e in results:
        cells = [f"{e['by'][b]['judge']} {e['by'][b]['ms']}ms" for b in backends]
        print(f"| {e['text']} | {'정상' if e['is_normal'] else e['expected']} | " + " | ".join(cells) + " |")
    print("| **규칙 적중** | | " + " | ".join(f"**{summary[b]['rule_hit']}**" for b in backends) + " |")
    print("| **정상 문장 유지** | | " + " | ".join(summary[b]["normal_kept"] for b in backends) + " |")
    print("| **평균 응답** | | " + " | ".join(f"{summary[b]['avg_ms']}ms" for b in backends) + " |")
    print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
