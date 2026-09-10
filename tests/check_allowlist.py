"""
검증 허용 목록 점검 — tutor.py 의 _pair_problem 이 쓰는 허용 목록(_allow, errors.jsonl 에서 생성)이 데이터를 얼마나 덮는지 본다.
LLM·임베딩 호출 없음. 몇 초면 끝난다.

    python -m tests.check_allowlist            # 요약
    python -m tests.check_allowlist --show     # 데이터에서 만든 목록 전부 출력

세 가지를 본다:
  1. errors.jsonl 의 정답 고침(target→fix) 400행을 _pair_problem 에 넣었을 때 거절되는 행 — 0 이어야 정상.
     거절되면 코드가 아니라 그 행(또는 그 규칙의 예시)을 고친다.
  2. 가짜 답(모델이 지어낸 고침)은 여전히 거절되는지 — 검증이 느슨해지지 않았다는 확인.
  3. 아직 코드에만 있는 것(_IRREGULAR_BASE 중 데이터에 없는 쌍, 오답 예시가 3행 미만인 규칙) — 데이터팀 안건.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import golden, tutor                                 # noqa: E402

# (학생 문장, wrong, fix, 규칙 유형, 규칙 id, 기대) — 기대 True = 통과해야 함, False = 거절해야 함
CASES = [
    ("I go to the zoo yesterday.", "go", "went", "과거시제", "R-31", True),
    ("I sorry.", "I sorry", "I am sorry", "형용사+be동사", "R-01", True),
    ("This is grandmother.", "grandmother", "my grandmother", "소유격", "R-03", True),
    ("This is sunny today.", "This", "It", "비인칭주어 it(날씨)", "R-14", True),
    ("I talk of my dog.", "of", "about", "전치사+명사", "R-27", True),
    ("Good morning Mom.", "Good morning Mom", "Good morning, Mom!", "인사말 문장부호", "R-02", True),
    ("It is very too hot.", "very too", "too", "too+형용사", "R-28", True),
    ("I went to go to the zoo.", "went to go", "went", "규칙 밖", "OTHER", True),
    ("I like playing.", "playing", "playing baseball", "like+동명사", "R-19", True),      # R-19 예시에만 있는 단어 → 그 규칙일 때만
    ("I like playing.", "playing", "playing baseball", "과거시제", "R-31", False),        # 다른 규칙이면 지어낸 단어
    ("I go to the zoo yesterday.", "yesterday", "saw", "과거시제", "R-31", False),        # 문장 다른 곳 단어 끌어옴
    ("I go to the zoo lastyear.", "lastyear", "yesterday", "과거시제", "R-31", False),    # 다른 단어로 교체
    ("I sorry.", "I sorry", "I am very sorry", "형용사+be동사", "R-01", False),          # 내용어 지어냄
    ("I have a dog.", "dog", "cat", "관사", "R-38", False),
    ("I go to the zoo yesterday.", "go to the zoo yesterday", "went to the zoo", "과거시제", "R-31", False),   # 시간 표현 없앰
    ("She like cats.", "like", "like", "3인칭단수", "R-32", False),                      # 고친 게 없음
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    al = tutor._allow()
    rules = {r["id"]: r for r in golden.rules()}
    errs = golden.errors()

    print(f"errors.jsonl {len(errs)}행 · rules {len(rules)}개")
    print(f"데이터에서 만든 허용 목록: 덧붙이는 단어 {len(al['added'])}개 (전 규칙) + 규칙별 {sum(len(v) for v in al['added_by_rule'].values())}개, "
          f"교체 쌍 {sum(len(v) for v in al['swap'].values()) // 2}개 (전 규칙) + 규칙별 {sum(len(b) for v in al['swap_by_rule'].values() for b in v.values()) // 2}개")
    if args.show:
        print("  덧붙이는 단어(전 규칙):", sorted(al["added"]))
        only = {k: sorted(v - al["added"]) for k, v in al["added_by_rule"].items() if v - al["added"]}
        print("  규칙별로만 허용:", only)
        print("  교체 쌍(전 규칙):", sorted((a, b) for a, bs in al["swap"].items() for b in bs if a < b))
        print("  규칙별로만 허용하는 교체:", {k: sorted((a, b) for a, bs in v.items() for b in bs if (b not in al["swap"].get(a, set()))) for k, v in al["swap_by_rule"].items()})

    # 1. 데이터 정답이 거절되는가
    rejected = []
    for e in errs:
        rt = rules.get(e["rule_id"], {}).get("type", "")
        p = tutor._pair_problem(e["error"], e["target"], e["fix"], rt, e["rule_id"])
        if p:
            rejected.append((e["id"], e["rule_id"], e["target"], e["fix"], p))
    print(f"\n1. 데이터 정답 400행 중 거절: {len(rejected)}건" + (" ✓" if not rejected else ""))
    for r in rejected:
        print(f"   {r[0]} {r[1]} {r[2]!r}→{r[3]!r}: {r[4]}")

    # 2. 가짜 답은 여전히 거절되는가
    wrong_cases = []
    for text, w, f, rt, rid, expect in CASES:
        p = tutor._pair_problem(text, w, f, rt, rid)
        if (p is None) != expect:
            wrong_cases.append((text, w, f, rid, expect, p))
    print(f"2. 가짜 답·정당한 답 케이스 {len(CASES)}개 중 틀린 판정: {len(wrong_cases)}건" + (" ✓" if not wrong_cases else ""))
    for c in wrong_cases:
        print(f"   {c[0]!r} {c[1]!r}→{c[2]!r} ({c[3]}) 기대={'통과' if c[4] else '거절'} 실제={c[5] or '통과'}")

    # 3. 아직 코드에만 있는 것
    data_pairs = {(a, b) for a, bs in al["swap"].items() for b in bs} | {(a, b) for v in al["swap_by_rule"].values() for a, bs in v.items() for b in bs}
    base_pairs = {(a, b) for a, bs in tutor._IRREGULAR_BASE.items() for b in bs}
    uncovered = sorted(base_pairs - data_pairs)
    per_rule = Counter(e["rule_id"] for e in errs)
    thin = [(rid, per_rule.get(rid, 0)) for rid in rules if per_rule.get(rid, 0) < 3]
    print(f"3. 코드에만 있는 불규칙 쌍: {len(uncovered)}/{len(base_pairs)} (데이터에 오답 예시가 생기면 표에서 뺄 수 있음)")
    print("   오답 예시 3행 미만 규칙 (규칙 연습도 못 만드는 규칙 — 데이터팀 안건):", ", ".join(f"{rid}({n})" for rid, n in thin) or "없음")
    if args.show:
        print("   불규칙 쌍:", uncovered)

    if rejected or wrong_cases:
        sys.exit(1)


if __name__ == "__main__":
    main()
