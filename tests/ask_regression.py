"""ask.py 회귀 테스트 (TTS 담당 소유) — /ask 의 실제 사용자 시나리오를 실제 backend.ask.ask()로
불러서 확인한다. 계약 문서(docs/2026.09.14 검색 함수 계약.md) 2-2절 "TTS 담당 수정 목록" 1~9번
반영 확인 + 2026-09-16 유닛/오답노트 화면 실사용 테스트로 발견한 버그들의 재발 방지용.

실행 (project 폴더에서, 가상환경 활성화 후):
    python -m tests.ask_regression

.env 의 LLM_BACKEND/EMBEDDING_BACKEND 그대로 사용 — 강의실 서버가 켜져 있으면 그걸로, 꺼져있으면
로컬/gemini 폴백으로 돈다(속도만 다르고 결과는 같아야 함). 로컬 e5-base로 여러 번 임베딩을 반복
호출하면 sentence-transformers 쪽 SystemError가 간헐적으로 나는 게 알려진 환경 문제라(2026-09-16),
이 스크립트가 실패하면 먼저 개별 항목만 다시 돌려서 진짜 회귀인지 환경 문제인지 확인할 것.

student ID는 항목마다 (질문, 옵션) 조합으로 해시해서 새로 만든다 — 같은 학생이 여러 항목에 겹치면
_recent_chat_turns 의 대화 맥락(180초 윈도우)이 섞여 오답이 난다(2026-09-16, 이어가기 항목에서
재현됐던 문제 — 이어가기를 실제로 테스트할 항목은 student를 명시적으로 고정해서 순서대로 부른다).

student "A" 는 data/student/ 의 실제(개발용) 오답노트 데이터를 쓴다 — R-31(과거시제)·R-08(This/
These) 등 여러 규칙이 쌓여 있다는 전제로 오답노트 요약 테스트를 만들었다. 그 데이터가 나중에
줄어들면(정리되면) 관련 항목이 깨질 수 있으니, 정확한 횟수가 아니라 "규칙이 최소 2개 이상"처럼
구조적인 조건만 확인한다.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.ask import ask, AskIn, AskContext, _retrieval_answer, _NOTEBOOK_TRIGGER  # noqa: E402
from backend.student import notebook_summary  # noqa: E402
import backend.ask as askmod  # noqa: E402

results: list[tuple[str, str, bool, str]] = []


def check(item: str, desc: str, cond: bool, detail: str = "") -> None:
    results.append((item, desc, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {item}. {desc}  {detail}")


def a(student: str, q: str, **ctx) -> dict:
    return ask(AskIn(student=student, question=q, context=AskContext(**ctx)))


# ── 계약 문서 TTS 담당 수정 목록 1~9번 ──────────────────────────────────────
check("1", "ask()가 _hybrid_answer()를 부름", "_hybrid_answer(body)" in inspect.getsource(askmod.ask))

r = a("C1_RULE_ALIAS", "과거시제가 뭐예요?")
check("2", "규칙 별칭으로 R-31 찾음", r["offtopic"] is False and any(s["chunk_id"] == "R-31" for s in r["source"]))

check("3a", "인사 고정답", "안녕" in a("C3A", "안녕!")["answer"])
check("3b", "감사 고정답", "천만" in a("C3B", "고마워")["answer"])
r_ctx = a("C3C", "과거시제가 뭐예요?")
r_follow = a("C3C", "다른 예문 보여줘")
check("3c", "이어가기가 직전 규칙 재사용", r_follow["offtopic"] is False and any(s["chunk_id"] == "R-31" for s in r_follow["source"]))
check("3d", "일상 잡담 거절", a("C3D", "오늘 날씨 어때?")["offtopic"] is True)

check("4a", "영어->뜻", "버스" in a("C4A", "bus가 뭐예요?")["answer"])
check("4b", "한국어->영어(역방향)", "brother" in a("C4B", "형이 영어로 뭐야?")["answer"])

q5 = "선생님을 만나면 인사한다는 문장이 뭐예요?"
r_l3 = _retrieval_answer(q5, AskIn(student="C5L3", question=q5, context=AskContext(level=3)), skip_similar=True)
r_l6 = _retrieval_answer(q5, AskIn(student="C5L6", question=q5, context=AskContext(level=6)), skip_similar=True)
check("5", "level=3 못찾음/level=6 찾음", r_l3["offtopic"] is True and r_l6["offtopic"] is False)

src_retrieval = inspect.getsource(askmod._retrieval_answer)
check("6", "sharp() 대신 절대점수(0.80/0.78) + 유닛 자료 보강 코드 존재",
      "0.80" in src_retrieval and "0.78" in src_retrieval and "golden.patterns(level" in src_retrieval)

r_unit = _retrieval_answer(q5, AskIn(student="C7", question=q5, context=AskContext(level=6, unit="Unit10")), skip_similar=True)
check("7", "다른 유닛 안내 문구", r_unit["answer"].startswith("Unit01에서 배우는 내용이에요"))

check("8", "FAQ 문턱 미달 rule_ids 폴백 코드 없음", 'faq_hits[0]["rule_ids"] if faq_hits else []' not in src_retrieval)

check("9a", "_answer() 완전히 삭제됨", not hasattr(askmod, "_answer"))
check("9b", "RETRIEVAL_PROMPT가 {grade} 변수 사용(3~4학년 하드코딩 아님)",
      "{grade}" in askmod.RETRIEVAL_PROMPT and "3~4학년" not in askmod.RETRIEVAL_PROMPT)
check("9c", "CORRECTNESS_PROMPT도 {grade} 변수 사용", "{grade}" in askmod.CORRECTNESS_PROMPT)


# ── 2026-09-16 유닛 화면 실사용 테스트로 발견·수정한 것들 ───────────────────
r_bus_diff = a("U1_DIFF", "bus가 뭐예요?", unit="Unit01", level=3)
check("U1", "다른 유닛 단어 조회에 안내 붙음(bus는 Unit15)", r_bus_diff["answer"].startswith("Unit15에서 배우는 내용이에요"))

r_bus_same = a("U1_SAME", "bus가 뭐예요?", unit="Unit15", level=3)
check("U2", "같은 유닛 단어 조회엔 안내 없음", not r_bus_same["answer"].startswith("Unit"))

r_all = a("U3_ALL", "과거시제가 뭐예요?", unit="Unit03", level=3)
check("U3", 'unit="ALL" 규칙은 안내 안 붙음(R-31)', "ALL에서 배우는 내용" not in r_all["answer"])

a("U4_DUP", "과거시제가 뭐예요?", unit="Unit05", level=3)
r_dup = a("U4_DUP", "다른 예문 보여줘", unit="Unit05", level=3)
check("U4", "예문 중복 없음(같은 문장 두 번 아님)",
      r_dup["answer"].count("I went to the zoo yesterday.") <= 1)


# ── 2026-09-16 오답노트 화면 실사용 테스트로 발견·수정한 것들 ───────────────
check("N1", '"틀려" 활용형도 오답노트 질문으로 인식', bool(_NOTEBOOK_TRIGGER.search("왜 자꾸 틀려?")))

r_empty = a("N2_EMPTY_NEVER_USED_BEFORE", "틀린 거 알려줘", screen="notebook")
check("N2", "빈 오답노트 안내(틀린 거 알려줘도 걸림)", "아직 오답노트에 기록된 게 없어요" in r_empty["answer"])

book_a = notebook_summary("A", max_examples=1)
if len(book_a["active"]) >= 2:
    r_summary = a("A", "내가 뭘 자주 틀려?", screen="notebook")
    check("N3", "일반 요약 질문에 답함(student A)",
          r_summary["offtopic"] is False and sum(1 for s in r_summary["source"] if s["chunk_id"].startswith("R-")) >= 2)
    check("N3b", "요약 답변에 규칙별 suggested 칩 있음", len(r_summary.get("suggested") or []) >= 2)

    r_ambiguous = a("A", "이거 왜 틀렸어?", screen="notebook")
    check("N4", "여러 규칙 요약 뒤 모호한 이어가기는 되물음",
          "얘기야" in r_ambiguous["answer"] and r_ambiguous["source"] == [])
else:
    check("N3", "일반 요약 질문에 답함(student A)", False, "SKIP — data/student/notebook.json 의 A 데이터가 부족함(2개 미만)")
    check("N4", "여러 규칙 요약 뒤 모호한 이어가기는 되물음", False, "SKIP — 위와 같은 이유")

r_specific = a("A", "관사 틀렸었나?", screen="notebook")
check("N5", "구체적 문법 주제는 그 규칙으로 직접 답(회귀 확인)",
      r_specific["offtopic"] is False and any(s["chunk_id"] == "R-38" for s in r_specific["source"]))


# ── 2026-09-16 정오 판정 검색 축소(ctx8k 컨텍스트 절약) ─────────────────────
r_corr = a("C_NARROW", "He like pizza. 이거 맞아?")
check("C1", "정오 판정이 검색 축소 후에도 정답 규칙(R-32) 찾음",
      r_corr["offtopic"] is False and any(s["chunk_id"] == "R-32" for s in r_corr["source"]))

from backend.ask import _correctness_candidate_rules  # noqa: E402
from backend import golden as _golden  # noqa: E402
narrowed = _correctness_candidate_rules("He like pizza")
# k=8 검색 후보 + unit="ALL" 공통 규칙(강제 포함, 100개 중 10개) 합친 크기라 <=8은 아니지만
# 규칙 전체(100개)보다는 훨씬 적어야 한다(2026-09-16, ALL 강제 포함 추가로 기준 조정).
check("C2", "정오 판정용 규칙 후보가 100개 전체가 아니라 좁혀짐",
      narrowed is not None and len(narrowed) < len(_golden.rules()) / 2,
      f"(len={len(narrowed) if narrowed else 0})")

all_ids = {r["id"] for r in _golden.rules() if r.get("unit") == "ALL"}
check("C3", "unit=ALL 공통 규칙은 검색 순위와 무관하게 항상 포함",
      narrowed is not None and all_ids <= {r["id"] for r in narrowed})


# ── 2026-09-16 유닛/오답노트 화면 반복 사용자 테스트로 발견·수정한 것들 ──────
check("D1", '"안녕하세요"(존댓말)도 인사 고정답으로 인식', "안녕" in a("D1", "안녕하세요")["answer"])

r_gowent = a("D2", "go랑 went 뭐가 달라요?")
check("D2", '영단어 2개 이상 질문은 FAQ가 그 전부와 안 겹치면 폐기(go+ing FAQ 오매칭 방지)',
      not any(s.get("chunk_id") == "F-93" for s in r_gowent["source"]))
r_inon = a("D2b", "in이랑 on 차이가 뭐예요?")
check("D2b", "위 필터 강화 후에도 진짜 다단어 매칭(in/on)은 회귀 없음",
      r_inon["offtopic"] is False and "in" in r_inon["answer"].lower())

r_unknown_topic = a("A", "관계대명사 틀렸었나?", screen="notebook")
check("D3", "오답노트에 없는 구체적 주제를 물으면 다른 주제로 안 바꿔치기하고 정직하게 답",
      "없어요" in r_unknown_topic["answer"] and r_unknown_topic["source"] == [])


print("\n=== 요약 ===")
passed = sum(1 for _, _, c, _ in results if c)
print(f"{passed}/{len(results)} 통과")
for item, desc, cond, detail in results:
    if not cond:
        print(f"  실패: {item}. {desc} {detail}")
