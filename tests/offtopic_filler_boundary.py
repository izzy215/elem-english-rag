"""오프토픽 판정·필러 오타 경계 전용 회귀 테스트 (TTS 담당 소유).

100문항 수동 테스트(tests/manual_chat_sessions.txt)에서 "오프토픽 오탐"·"오타에 약함"이
반복적으로 나와서(2026-09-16), 그 경계만 따로 촘촘히 확인한다. ask_regression.py처럼
student마다 이어가기 맥락이 안 섞이게 질문마다 새 student id를 쓴다.

실행 (project 폴더에서, 가상환경 활성화 후):
    python -m tests.offtopic_filler_boundary
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.ask import ask, AskIn, AskContext  # noqa: E402

results: list[tuple[str, str, bool, str]] = []


def check(item: str, desc: str, cond: bool, detail: str = "") -> None:
    results.append((item, desc, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {item}. {desc}  {detail}")


def a(q: str, **ctx) -> dict:
    return ask(AskIn(student="OFB_" + str(abs(hash(q))), question=q, context=AskContext(**ctx)))


# ── A. 진짜 잡담 — offtopic=True 여야 함 ────────────────────────────────────
for i, q in enumerate([
    "오늘 날씨 어때?", "오늘 기분 어때?", "컨디션 어때?", "점심 뭐 먹었어?",
    "저녁 뭐 먹지?", "급식 뭐 나와?", "숙제 있어?", "지금 몇 시야?", "오늘 몇시야",
    "너 이름이 뭐야?", "너 몇 살이야?", "게임 추천해줘", "유튜브 뭐 볼까?", "심심해 뭐하지",
], start=1):
    r = a(q)
    check(f"A{i}", f'"{q}" 잡담 거절', r["offtopic"] is True, f"(answer={r['answer'][:40]!r})")


# ── B. 잡담처럼 보이지만 영어가 섞인 진짜 학습 질문 — offtopic=False 여야 함
#      (_casual_chat_reject의 "[A-Za-z]|영어 있으면 안 걸림" 가드 확인) ──────
# "기분"(mood)·"lunch"는 words.csv에 아예 없는 단어라(2026-09-16 확인) 애초에 offtopic=True가
# 맞는 답 — 가드 자체가 아니라 교재에 없는 단어를 테스트에 잘못 고른 것이었다. 가드가 실제로
# 하는 일만 확인하려면 교재에 있는 단어로 테스트해야 한다.
for i, (q, note) in enumerate([
    ("날씨를 영어로 어떻게 말해요?", "날씨+영어, weather는 words.csv에 있음"),
], start=1):
    r = a(q)
    check(f"B{i}", f'"{q}" ({note}) 잡담으로 안 걸리고 답함', r["offtopic"] is False, f"(answer={r['answer'][:40]!r})")


# ── C. 필러 표현 오타·붙여쓰기 — 정타와 같은 결과(offtopic=False)여야 함 ─────
for i, (q, note) in enumerate([
    ("과거시제가 모에요?", "뭐예요→모에요"),
    ("bus가 머예요?", "뭐예요→머예요"),
    ("소유격이 뭐에요?", "예요→에요"),
    ("water 이거 머임?", "뭐임→머임 + '이거'가 영단어와 같이 있으면 임베딩 유사도가 떨어지는 문제"),
], start=1):
    r = a(q)
    check(f"C{i}", f'"{q}" ({note}) 필러 오타에도 정상 답변', r["offtopic"] is False, f"(answer={r['answer'][:40]!r})")

# "모임"(gathering)은 "머임"과 한 글자 차이지만 진짜 단어라 안 망가져야 함 — words.csv에
# "모임"/meeting 자체가 없어서 ask() 전체로 확인하면 (다른 이유로) 어차피 거절되니, 정규화
# 함수만 직접 불러 문자열이 안 바뀌는지로 확인한다("머임"만 좁게 잡고 "모임"은 안 건드리게 함).
from backend.ask import _normalize_filler_typos  # noqa: E402
check("C-safe", '"모임이 영어로 뭐예요?"(진짜 단어)가 "머임" 치환에 안 망가짐',
      _normalize_filler_typos("모임이 영어로 뭐예요?") == "모임이 영어로 뭐예요?")

# 영단어 없이 순수 이어가기("이거 왜 틀렸어?")는 "이거" 제거 가드에 안 걸려야 함(회귀) —
# 이 가드는 re.search([A-Za-z])가 있을 때만 동작하므로 여기선 안 걸리는 게 맞다.
r_pure_ref = a("이거 왜 틀렸어?", screen="notebook")
check("C-safe2", '"이거 왜 틀렸어?"(영단어 없음)는 지시어 제거 가드 영향 없이 그대로 동작',
      True, f"(offtopic={r_pure_ref['offtopic']}, answer={r_pure_ref['answer'][:40]!r}) — 정보용, 맥락 없어 통과 실패해도 무방")


# ── D. 모/머로 시작하는 진짜 단어 — 필러 정규화가 안 망가뜨려야 함 ──────────
for i, (q, note) in enumerate([
    ("이모가 영어로 뭐예요?", "이모(aunt) — 모+가"),
    ("모자가 영어로 뭐예요?", "모자(hat) — 모+자"),
    ("머리가 영어로 뭐예요?", "머리(head) — 머+리"),
], start=1):
    r = a(q)
    check(f"D{i}", f'"{q}" ({note}) 진짜 단어 안 망가짐', r["offtopic"] is False, f"(answer={r['answer'][:50]!r})")


# ── E. 규칙명 자체의 오타 — 편집거리 폴백으로 구제되어야 함 ─────────────────
for i, (q, expect_rule, note) in enumerate([
    ("괴거시제가 뭐예요?", "R-31", "과거→괴거"),
    ("소유격이 모예요?", "R-03", "필러+어미만 오타(회귀, 규칙명은 정타)"),
], start=1):
    r = a(q)
    got = any(s.get("chunk_id") == expect_rule for s in r["source"])
    check(f"E{i}", f'"{q}" ({note}) {expect_rule}로 구제됨', r["offtopic"] is False and got, f"(source={r['source']})")

# 알려진 한계 — 2글자 규칙명(관사·소유격)의 1글자 오타는 편집거리 문턱(0.6)을 못 넘어
# 구제 안 됨(간사↔관사=0.4, 소요격↔소유격=0.571, 둘 다 문턱 미달, 2026-09-16 실측). 문턱을
# 낮추면 "미래시제"·"과거시제"(0.44) 같은 진짜 다른 개념끼리 섞일 위험이 커져서 보수적으로 둔다.
r_known = a("간사가 뭐예요?")
check("E-known-limit", '"간사가 뭐예요?"(관사 오타, 2글자)는 아직 구제 안 됨 — 의도된 한계, 회귀 아님',
      r_known["offtopic"] is True, f"(answer={r_known['answer'][:40]!r})")


# ── F. 진짜 다른 개념끼리 안 섞이는지(오검출 방지) ──────────────────────────
r_future = a("미래시제가 뭐예요?")
check("F1", '"미래시제가 뭐예요?"가 과거시제(R-31)로 잘못 답하지 않음(둘 다 오답 없음 허용, 섞이면 실패)',
      not any(s.get("chunk_id") == "R-31" for s in r_future["source"]), f"(source={r_future['source']})")

r_correct_past = a("과거시제가 뭐예요?")
check("F2", '(회귀) 정타 "과거시제가 뭐예요?"는 여전히 R-31로 정상 답변',
      r_correct_past["offtopic"] is False and any(s.get("chunk_id") == "R-31" for s in r_correct_past["source"]))


print("\n=== 요약 ===")
passed = sum(1 for _, _, c, _ in results if c)
print(f"{passed}/{len(results)} 통과")
for item, desc, cond, detail in results:
    if not cond:
        print(f"  실패: {item}. {desc} {detail}")
