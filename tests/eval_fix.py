"""
Gemini vs 선생님 서버 로컬 모델 비교 실험 (docs/plan-B/local-llm-plan.md 작업 4)   담당: 팀장

data/golden/eval.csv (없으면 _sample-B/eval.csv) 의 문장들을 tutor.py 와 똑같은 프롬프트·
규칙 조각(rules.jsonl 전체)으로 만들어 Gemini 와 로컬 모델에 각각 보내고, 규칙 적중·고친 문장
일치·정상 문장 오교정·응답 시간을 표로 만든다. "근거 조각을 주면 소형 모델도 맞게 고치나"의 증거.

실행 (프로젝트 루트에서):
    .venv\\Scripts\\python.exe -m tests.eval_fix

로컬 모델을 같이 보려면 .env 의 LLM_LOCAL_URL 이 채워져 있고 그 주소에 실제로 닿아야 한다
(선생님 서버 SSH 터널 예: ssh -L 11434:localhost:11434 research1@192.168.1.147).
LLM_LOCAL_URL 이 비어 있거나 안 닿으면 로컬 칸은 오류로 표시되고 Gemini 결과만 채워진다.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from backend import llm, tutor
from backend.config import settings

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "rag_eval"
OUT_FILE = OUT_DIR / "fix_compare.json"


def _eval_csv_path() -> Path:
    real = tutor.GOLDEN / "eval.csv"
    return real if real.exists() else tutor.SAMPLE_B / "eval.csv"


def _load_cases() -> list[dict]:
    with _eval_csv_path().open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _build_prompt(text: str) -> str:
    """tutor.fix() 와 완전히 같은 프롬프트 조립(규칙 전체·미션 없음)을 재사용한다 — '같은 근거'가 실험의 전제."""
    return tutor._render(
        tutor.PROMPT_FILE.read_text(encoding="utf-8"),
        mission="(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words="(없음)",
        all_rules=tutor._rules_block(tutor.rules()),
        sentence=text,
    )


def _call(prompt: str, backend: str) -> dict:
    t0 = time.time()
    try:
        out = llm.generate_json(prompt, backend=backend)
        return {
            "error": None,
            "rule_id": "NONE" if out.get("ok") else out.get("rule_id"),
            "fixed": out.get("fixed"),
            "ms": out.get("_llm", {}).get("ms", int((time.time() - t0) * 1000)),
        }
    except llm.LLMError as e:
        return {"error": str(e), "rule_id": None, "fixed": None, "ms": int((time.time() - t0) * 1000)}


def run() -> list[dict]:
    # 이 실험에서는 local 실패를 그대로 보고 싶다 (generate_json 기본 동작인 gemini 자동 대체가 켜져 있으면
    # local 칸이 항상 gemini 결과로 채워져 비교가 안 됨) — 이 프로세스 안에서만 끈다, .env·서버엔 영향 없음.
    object.__setattr__(settings, "llm_fallback", False)

    rows = []
    for case in _load_cases():
        text, expected = case["text"], case["expected_rule_id"]
        prompt = _build_prompt(text)
        print(f"[eval] {text!r} (기대: {expected})", flush=True)
        gemini = _call(prompt, "gemini")
        if settings.llm_local_url:
            local = _call(prompt, "local")
        else:
            local = {"error": "LLM_LOCAL_URL 미설정", "rule_id": None, "fixed": None, "ms": 0}
        rows.append({"text": text, "expected_rule_id": expected, "note": case.get("note", ""),
                     "gemini": gemini, "local": local})
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    summary = {}
    for key in ("gemini", "local"):
        ok_rows = [r for r in rows if not r[key]["error"]]
        hits = sum(1 for r in ok_rows if (r[key]["rule_id"] or "NONE") == r["expected_rule_id"])
        false_pos = sum(1 for r in ok_rows if r["expected_rule_id"] == "NONE" and r[key]["rule_id"] not in ("NONE", None))
        times = [r[key]["ms"] for r in ok_rows]
        summary[key] = {
            "rule_hit": f"{hits}/{n}",
            "false_positives": f"{false_pos}/2",
            "avg_ms": int(sum(times) / len(times)) if times else None,
            "errors": n - len(ok_rows),
        }
    both_ok = [r for r in rows if not r["gemini"]["error"] and not r["local"]["error"]]
    agree = sum(1 for r in both_ok if (r["gemini"]["fixed"] or "").strip().lower() == (r["local"]["fixed"] or "").strip().lower())
    summary["gemini_local_fixed_agree"] = f"{agree}/{len(both_ok)}" if both_ok else "0/0"
    return summary


def to_markdown(rows: list[dict]) -> str:
    lines = ["| 문장 | 정답 규칙 | Gemini 규칙/고침/ms | 로컬 규칙/고침/ms |", "|---|---|---|---|"]
    for r in rows:
        g, l = r["gemini"], r["local"]
        g_cell = f"오류: {g['error'][:40]}" if g["error"] else f"{g['rule_id']} / {g['fixed']} / {g['ms']}ms"
        l_cell = f"오류: {l['error'][:40]}" if l["error"] else f"{l['rule_id']} / {l['fixed']} / {l['ms']}ms"
        lines.append(f"| {r['text']} | {r['expected_rule_id']} | {g_cell} | {l_cell} |")
    return "\n".join(lines)


def main() -> None:
    rows = run()
    summary = summarize(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(to_markdown(rows))
    print()
    for key in ("gemini", "local"):
        s = summary[key]
        print(f"{key}: 규칙 적중 {s['rule_hit']} · 오탐 {s['false_positives']} · 평균 {s['avg_ms']}ms · 오류 {s['errors']}건")
    print(f"두 모델 고친 문장 일치: {summary['gemini_local_fixed_agree']}")
    print(f"\n저장: {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
