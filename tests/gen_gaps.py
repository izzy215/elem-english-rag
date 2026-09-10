"""
"우리 규칙으로 못 짚은 문장" 모으기 — 명령줄. 본체는 backend/gapcheck.py (관리자 화면의 [생성 점검 실행] 버튼과 같은 코드).

    python -m tests.gen_gaps                     # .env 의 LLM_BACKEND 로 20문장 생성 → /fix → 로그 (student=GEN)
    python -m tests.gen_gaps --n 40
    python -m tests.gen_gaps --backend gemini    # 생성·진단 모두 이 백엔드로 (.env 는 안 바뀜). gemini 는 분당 한도 때문에 5초 간격
    python -m tests.gen_gaps --sleep 6           # 문장 사이 대기(초)
    python -m tests.gen_gaps --dry               # 생성만 하고 /fix 는 안 부름

결과: data/rag_eval/gen_gaps_<시각>.json + gen_gaps_latest.json (관리자 화면이 읽음). 학생 로그에는 student=GEN 으로 남는다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import gapcheck, llm                                  # noqa: E402
from backend.config import settings                               # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--student", default="GEN")
    ap.add_argument("--backend", default=None, help="gemini | claude | LLM_ENDPOINTS 이름 (기본 .env 의 LLM_BACKEND)")
    ap.add_argument("--sleep", type=float, default=None, help="문장 사이 대기 초 (gemini 기본 5, 그 외 0)")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    backend = args.backend or settings.llm_backend
    print(f"[gen_gaps] {backend}:{llm._model_of(backend)} 로 문장 {args.n}개 생성 중…", flush=True)
    if args.dry:
        for i, r in enumerate(gapcheck.generate(args.n, backend), 1):
            print(f"  [{i:2}] {'안' if r.get('inside') else '밖'} {r['text']!r} → {r.get('correct', '')!r}  ← {r.get('error', '')}")
        return
    marks = {"ok": "✓ ", "rule": "규칙", "OTHER": "밖 ", "fail": "실패", "llm_err": "호출오류"}
    out = gapcheck.run_check(n=args.n, backend=backend, student=args.student, sleep=args.sleep,
                             progress=lambda i, t, r: print(f"  [{i:2}/{t}] {marks[r['result']]} {r['text']!r:45} {r['detail']}   (모델 표시: {'안' if r['inside'] else '밖'} · {r['intended']})", flush=True))
    t = out["tally"]
    print(f"\n[gen_gaps] 맞음 {t['ok']} · 규칙으로 고침 {t['rule']} · 규칙 밖 {t['OTHER']} · 진단 실패 {t['fail']} · 호출 오류 {t['llm_err']}")
    print(f"[gen_gaps] 규칙 밖 오류로 만들었는데 튜터가 맞다고 한 문장 {len(out['missed_outside'])}개 = 빠진 규칙 후보 (모델 표시라 확인 필요):")
    for x in out["missed_outside"]:
        print(f"    - {x['text']}  ← {x['intended']}  (만든 모델의 정답: {x['correct'] or '?'})")
    print(f"[gen_gaps] 저장: {out['path']} (+ gen_gaps_latest.json → 관리자 화면)")


if __name__ == "__main__":
    main()
