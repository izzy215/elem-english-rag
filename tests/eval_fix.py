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

결과 (data/rag_eval/, git 제외) — 실행마다 시각이 붙은 새 파일 + 가장 최근 것의 복사본:
    fix_compare_20260908-1627.json   문장별 원본 응답 (고친 문장·full_fixed·ms 등)
    fix_compare_20260908-1627.md     발표 자료에 붙일 마크다운 표 (화면에도 같이 찍힘)
    fix_compare_latest.json / .md    가장 최근 실행의 복사본 (항상 덮어씀)
    --out 으로 이름을 직접 주면 그 이름으로만 저장 (latest 는 갱신 안 함)

오답노트·문장 로그에는 기록하지 않는다 (tutor.fix() 를 안 부르고 프롬프트 조립 + llm 호출만 한다).
비용: 문장 수 × 백엔드 수 만큼 LLM 호출. 무료 등급이면 한도 주의.
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

from backend import golden, llm, tutor                            # noqa: E402
from backend.config import settings                               # noqa: E402

OUT_DIR = ROOT / "data" / "rag_eval"


def load_eval() -> list[dict]:
    rows = golden.eval_set()
    for r in rows:
        r["expected_rule_id"] = (r.get("expected_rule_id") or "").strip()
        r["is_normal"] = r["expected_rule_id"] in ("", "NONE")
    return rows


def build_prompt(text: str, rules: list[dict], level: int = 2, unit: str = "U3") -> str:
    """tutor.fix() 와 똑같은 폴백 프롬프트 (규칙 전부). RAG 가 붙으면 candidates 를 검색 결과로 바꿔 'rag' 조건도 비교할 수 있다."""
    unit_row = golden.find_unit(level, unit) or {}
    return tutor._render(
        tutor.PROMPT_FILE.read_text(encoding="utf-8"),
        mission=unit_row.get("mission") or "(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words=", ".join(unit_row.get("hint_words") or []) or "(없음)",
        all_rules=tutor._rules_block(rules),
        sentence=text,
    )


def run_one(text: str, backend: str, rules: list[dict]) -> dict:
    prompt = build_prompt(text, rules)
    t0 = time.time()
    try:
        out = llm.generate_json(prompt, backend=backend, fallback=False)   # 비교 실험: 대체 금지. 실패는 실패로 기록
        info = out.pop("_llm", {})
        if info.get("fallback_from"):                            # 혹시라도 대체됐으면 실패로 취급
            raise llm.LLMError(f"{backend} 실패 → {info.get('backend')} 로 대체됨 (비교 실험에선 무효)")
        rule_id = None if out.get("ok") else out.get("rule_id")
        if rule_id and not golden.find_rule(rule_id):
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
    ap.add_argument("--out", default=None, help="저장 파일명 (기본: data/rag_eval/fix_compare_<시각>.json + _latest 복사본)")
    args = ap.parse_args()

    b = (args.backend or settings.llm_backend or "gemini").lower()
    backends = llm.backends() if b == "all" else [x.strip() for x in b.split(",") if x.strip()]
    rows = load_eval()
    if args.limit:
        rows = rows[: args.limit]
    rules = golden.rules()
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
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    if args.out is None:
        args.out = str(OUT_DIR / f"fix_compare_{stamp}.json")
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "prompt_file": tutor.PROMPT_FILE.name, "rules_n": len(rules),
           "backends": backends, "summary": summary, "results": results}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 마크다운 표 — 화면에 찍고 같은 이름의 .md 로도 저장 (발표 자료에 붙이기용)
    md_lines = [f"# /fix 비교 실험 — {out['ran_at']} · eval {len(rows)}문장 · 규칙 {len(rules)}개 · 프롬프트 {tutor.PROMPT_FILE.name}", ""]
    md_lines.append("| 문장 | 정답 | " + " | ".join(f"{b} ({summary[b]['model']})" for b in backends) + " |")
    md_lines.append("|---|---|" + "---|" * len(backends))
    for e in results:
        cells = [f"{e['by'][b]['judge']} {e['by'][b]['ms']}ms" for b in backends]
        md_lines.append(f"| {e['text']} | {'정상' if e['is_normal'] else e['expected']} | " + " | ".join(cells) + " |")
    md_lines.append("| **규칙 적중** | | " + " | ".join(f"**{summary[b]['rule_hit']}**" for b in backends) + " |")
    md_lines.append("| **정상 문장 유지** | | " + " | ".join(summary[b]["normal_kept"] for b in backends) + " |")
    md_lines.append("| **평균 응답** | | " + " | ".join(f"{summary[b]['avg_ms']}ms" for b in backends) + " |")
    md_lines += ["", "판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)",
                 "고친 문장 등 원본 응답은 같은 이름의 .json 참고."]
    md = "\n".join(md_lines)
    print("\n" + md)
    md_path = Path(args.out).with_suffix(".md")
    md_path.write_text(md + "\n", encoding="utf-8")
    print(f"\n저장: {args.out}\n      {md_path}")
    if Path(args.out).name == f"fix_compare_{stamp}.json":   # 기본 이름일 때만 latest 갱신
        for src, dst in ((Path(args.out), OUT_DIR / "fix_compare_latest.json"), (md_path, OUT_DIR / "fix_compare_latest.md")):
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"      {OUT_DIR / 'fix_compare_latest.md'} (최근 복사본)")


if __name__ == "__main__":
    main()
