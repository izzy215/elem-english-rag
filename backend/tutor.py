"""
튜터 — 내 문장 고쳐주기 (PRD 4.3)   담당: 팀장

POST /api/fix  {student, level, unit, text, source}
  → {ok, rule{id,name,score,rank}, runner_up, wrong, fix, fixed, why, source, more_errors, full_fixed, spelling,
     suggested_questions, mission, log_id, mode, fallback_reason, candidates, llm, timing}

동작:
  0. 철자 사전검사(_spell_precheck, pyspellchecker + 교재 단어) → 철자만 고친 문장으로 아래를 진행 (원문은 화면·로그용 orig)
  1. RAG 검색(rag.search_rules) 으로 규칙 전부를 점수순으로 받는다 (점수·순위 표시용).
     프롬프트에는 상위 RAG_TOP_K + 이 Unit 의 규칙(units.csv rule_ids) + 공통(unit=ALL) 규칙 + 가짜 규칙 SPELL·OTHER (mode="rag")
     검색 실패(색인 없음·임베딩 오류·결과 0)면 규칙 전부 (mode="fallback", fallback_reason="search_error" | "no_results")
  2. 오늘의 미션(units.csv)과 함께 프롬프트(prompts/fix_fallback.txt)에 넣어 LLM(backend/llm.py) 에 JSON 으로만 답하게 한다
  3. 검증: 규칙 id 가 전달한 근거 안인가, (wrong→fix) 가 학생 단어를 살린 고침인가(_pair_problem). 걸리면 1회 재생성,
     그래도 안 되면 full_fixed 가 학생 단어뿐일 때 '규칙 밖(OTHER)' 으로 살리고 아니면 502 (실패도 sentence_log 에 남김).
     철자 쌍이면 ok=true + spelling, 기능어 한 개 교체(is→are)는 _second_opinion 으로 한 번 더 확인, 고친 게 없는 답은 재시도 후 ok.
  4. 학생 DB 에 문장 로그 + 오답노트 기록 (fix_internal() 은 기록 없이 같은 결과 — 비교 실험용). timing 에 단계별 시간

threshold 는 아직 미설정 (RAG 담당 실측: 정상 문장이 오류 문장보다 검색 점수가 높음). 정오 판단은 모델의 ok 가 한다.
화면(frontend/js/tutor.js)은 이 응답 형식을 이미 기다리고 있다. 필드 이름을 바꾸면 화면도 같이 바꿔야 한다.

데이터 읽기는 전부 golden.py (TTS 팀원 소유, 공통): rules() · find_rule() · find_unit() · faqs() · known_english_vocab(). 골든/샘플 선택도 거기서 한다.
학생 DB: data/student/sentence_log.jsonl, notebook.json (PRD 5.2 형식, gitignore)
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import golden, llm
from backend.config import settings

ROOT = Path(__file__).resolve().parent.parent          # project/
STUDENT_DIR = ROOT / "data" / "student"
PROMPT_FILE = Path(__file__).parent / "prompts" / "fix_fallback.txt"

router = APIRouter(tags=["tutor"])
_lock = threading.Lock()
RAG_TOP_K = 5          # 규칙이 많을 때 프롬프트에 넣는 검색 후보 수 겸 응답 candidates·로그의 표시 개수. 어순 규칙이 4~5위로 나와 5 로 둔다
# 프롬프트에만 끼워 넣는 '철자' 규칙 (rules.jsonl·색인·평가에는 없음). 모델이 철자 실수를 문법 규칙으로 억지로 맞추지 않게 출구를 준다
# ('i hate vegetibals' 에서 hate→am 같은 답). 모델이 이 id 를 고르고 (wrong,fix) 가 한 단어 쌍이면 서버가 ok=true + 철자 안내로 바꾼다 (아니면 502).
SPELLING_RULE = {"id": "SPELL", "type": "철자", "unit": "ALL",
                 "text": "단어의 철자가 틀린 경우. 문법은 맞는데 글자만 틀렸으면 이 규칙을 고르고 wrong=틀린 철자, fix=맞는 철자. 틀린 예: I like aple."}
# 프롬프트에만 끼워 넣는 '규칙 밖' 출구. 참고 규칙 어디에도 안 맞는 문제(단어가 남거나 빠짐: 'I went to go to zoo')를 모델이 억지로
# 다른 규칙에 끼워 맞추지 않게 한다. 서버는 _student_words_only 를 통과한 문장(학생 단어·그 변형·기능어만, 2단어 넘게 안 늘어남)일 때만 받아서
# 규칙·오답노트 없이 "✎ 우리 규칙 밖이에요" 카드로 보여준다.
OTHER_RULE = {"id": "OTHER", "type": "규칙 밖", "unit": "ALL",
              "text": "참고 규칙 어디에도 맞지 않는 문제(단어가 남거나 빠짐 등). 이 규칙을 고르면 wrong·fix 는 null 로 두고, fixed 와 full_fixed 에 학생이 쓴 단어만으로 자연스럽게 고친 문장을 쓴다. 새 단어를 넣지 않는다."}
RAG_ALL_IF_LE = 12     # 규칙이 이 수 이하(샘플 9개)면 검색으로 후보를 좁히지 않고 전부 넣는다. 화면·로그엔 상위 RAG_TOP_K 만 표시
# 규칙이 많을 때(실제 38개) 프롬프트 = 검색 상위 RAG_TOP_K + 이 Unit 의 규칙(units.csv rule_ids) + 공통(unit=ALL) 규칙.
# 검색만으로는 관사(R-38) 같은 공통 규칙이 후보 밖으로 밀린다 ('I drew zoo yesterday' 에서 R-38 이 22위) → 관사를 붙였다 안 붙였다 하는 원인


# ─────────────────────────────────────────────
# 프롬프트 · Gemini
# ─────────────────────────────────────────────
def _render(template: str, **vars_: str) -> str:
    for k, v in vars_.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def _rules_block(rule_list: list[dict]) -> str:
    return "\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in rule_list)


def _ask_llm(prompt: str, backend: str | None = None, fallback: bool | None = None, timing: dict | None = None) -> dict:
    """JSON 만 받는다. 어느 모델(Gemini/로컬)을 쓸지는 backend/llm.py 와 .env 의 LLM_BACKEND 가 정한다.
    backend·fallback 은 비교 실험(tests/eval_fix.py)이 호출별로 지정할 때만 쓴다 — 서비스 경로는 None. timing 이 있으면 호출 시간·횟수를 누적."""
    t0 = time.perf_counter()
    try:
        return llm.generate_json(prompt, backend=backend, fallback=fallback)
    finally:
        if timing is not None:
            timing["llm_ms"] += int((time.perf_counter() - t0) * 1000)
            timing["llm_calls"] += 1


def _tidy(sentence: str) -> str:
    """표기 통일: 앞뒤 공백 제거, 첫 글자 대문자, 끝에 문장부호 없으면 마침표."""
    out = (sentence or "").strip()
    if not out:
        return out
    out = out[0].upper() + out[1:]
    return out if out[-1] in ".!?" else out + "."


_DUP = re.compile(r"\b(\w+)\s+\1\b", flags=re.IGNORECASE)   # 'to to', 'the the' 같은 겹말
_BAD_ART = re.compile(r"\b(a|an|the)\s+(a|an|the)\b", flags=re.IGNORECASE)   # 'a an elephant' — 모델이 관사 빼고 wrong 범위를 잡았을 때


def _broken(sentence: str) -> bool:
    """한 곳만 바꾼 결과가 겹말·관사 겹침으로 깨졌는지."""
    return bool(_DUP.search(sentence) or _BAD_ART.search(sentence))


def _single_fix(text: str, wrong: str | None, fix: str | None) -> str | None:
    """학생 문장에서 wrong 한 단어(구)만 fix 로 바꾼 문장. wrong 이 문장에 없으면 None.
    모델이 지시를 어기고 여러 곳을 한꺼번에 고쳐 와도, 화면에는 '1위 규칙 하나만 고친 문장' 을 보여 주기 위해 서버가 다시 만든다.
    그래야 [다시 고쳐줘] 2차에서 나머지 오류가 실제로 잡힌다 (PRD 7: 1위만 고치고 more_errors)."""
    if not wrong or not fix:
        return None
    m = re.search(r"(?<![A-Za-z])" + re.escape(wrong.strip()) + r"(?![A-Za-z])", text, flags=re.IGNORECASE)
    if not m:
        return None
    out = text[: m.start()] + fix.strip() + text[m.end():]
    out = out.strip()
    out = out[0].upper() + out[1:]                       # 문장 첫 글자 대문자 (문법 아님, 보기용)
    if out and out[-1] not in ".!?":
        out += "."
    return out


_ARTICLES = {"a", "an", "the"}
# 불규칙 변화 (어간이 안 겹치는 것들). 그 외 한 단어 교체는 어간(앞 2글자)이 같아야 "같은 단어의 변형" 으로 본다
_IRREGULAR = {"go": {"went", "goes", "going"}, "see": {"saw", "sees", "seeing"}, "eat": {"ate", "eats", "eating"}, "have": {"had", "has", "having"},
              "do": {"did", "does", "doing"}, "am": {"was", "is", "are"}, "is": {"was", "am", "are"}, "are": {"were", "am", "is"}, "was": {"were", "am", "is"},
              "were": {"was", "are"}, "be": {"am", "is", "are", "was", "were"}, "run": {"ran"}, "come": {"came"}, "take": {"took"}, "give": {"gave"},
              "make": {"made"}, "get": {"got"}, "buy": {"bought"}, "drink": {"drank"}, "swim": {"swam"}, "sing": {"sang"},
              "sit": {"sat"}, "write": {"wrote"}, "ride": {"rode"}, "ring": {"rang"}, "begin": {"began"}, "meet": {"met"}, "feel": {"felt"},
              "keep": {"kept"}, "sleep": {"slept"}, "leave": {"left"}, "bring": {"brought"}, "think": {"thought"}, "catch": {"caught"},
              "teach": {"taught"}, "tell": {"told"}, "sell": {"sold"}, "find": {"found"}, "stand": {"stood"}, "win": {"won"}, "know": {"knew"},
              "grow": {"grew"}, "throw": {"threw"}, "draw": {"drew"}, "fly": {"flew"}, "wear": {"wore"}, "speak": {"spoke"}, "break": {"broke"},
              "drive": {"drove"}, "hear": {"heard"}, "say": {"said"}, "pay": {"paid"}, "read": {"read"}, "lose": {"lost"}, "send": {"sent"},
              "build": {"built"}, "hold": {"held"}, "fall": {"fell"}, "forget": {"forgot"}, "hide": {"hid"}, "bite": {"bit"}, "feed": {"fed"},
              "this": {"these"}, "these": {"this"}, "that": {"those"}, "those": {"that"}, "much": {"many"}, "many": {"much"},
              "a": {"an", "the"}, "an": {"a", "the"}, "the": {"a", "an"}, "child": {"children"}, "man": {"men"}, "woman": {"women"}, "foot": {"feet"}, "tooth": {"teeth"}, "mouse": {"mice"}}
_TIME_WORDS = {"yesterday", "today", "tomorrow", "now", "ago", "last", "next", "week", "year", "month", "morning", "night"}   # 우리 규칙은 시간 표현을 바꾸지 않는다


def _tokens(t: str) -> list[str]:
    return re.findall(r"[a-z']+", (t or "").lower())


# 규칙이 "덧붙일 수 있는" 기능어. be동사 추가(I sorry→I am sorry), 관사 추가(lion→a lion), 전치사·조동사 추가(go zoo→go to the zoo).
# 이 밖의 새 단어(내용어)가 fix 에 들어오면 학생이 안 쓴 말을 지어낸 것으로 보고 거절한다.
_FUNC_WORDS = _ARTICLES | {"am", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "will", "can", "not",
                           "to", "in", "on", "at", "under", "of", "for", "with", "by", "there", "much", "many", "some", "any", "and"}


def _related(a: str, b: str) -> bool:
    """같은 단어의 변형인가 (draw/drew, eat/eating, lion/lions, read/red 같은 철자 차이 포함). 어간 앞 2글자 또는 불규칙표."""
    return a == b or (len(a) >= 2 and a[:2] == b[:2]) or b in _IRREGULAR.get(a, set()) or a in _IRREGULAR.get(b, set())


def _pair_problem(text: str, wrong: str | None, fix: str | None, rule_type: str = "") -> str | None:
    """모델이 준 (wrong → fix) 쌍이 '학생 단어를 규칙에 맞게 고친 것' 인지 확인. 문제가 있으면 이유 문자열, 없으면 None.
    허용: 변형(draw→drew, eat→is eating), 기능어 추가(lion→a lion, I sorry→I am sorry, go zoo→go to the zoo), 어순 규칙의 재배열.
    거절: 다른 단어로 교체(lastyear→yesterday), 문장 다른 곳 단어를 끌어옴(yesterday→saw = 어순 바꾸기 시도), 내용어를 새로 지어냄.
    wrong 은 최대 4단어, 시간 표현(yesterday/tomorrow …)은 학생의 뜻이라 바꾸는 답을 거절한다.
    규칙 38개 기준으로 다시 짬 — 예전 '한 단어만' 기준은 be동사·전치사 추가 규칙(R-01·R-17·R-24·R-35 …)을 전부 거절했다."""
    if not wrong or not fix:
        return "wrong/fix 비어 있음"
    w, f = _tokens(wrong), _tokens(fix)
    if not w or not f:
        return "wrong/fix 가 단어가 아님"
    if not re.search(r"(?<![A-Za-z])" + re.escape(wrong.strip()) + r"(?![A-Za-z])", text, flags=re.IGNORECASE):
        return f"wrong={wrong!r} 이 학생 문장에 없음"
    if wrong.strip() == fix.strip():                         # drew → drew 처럼 고친 게 없는 쌍 (모델이 더 고칠 게 없는데 ok=false 로 답함)
        return f"wrong 과 fix 가 같음: {wrong!r}"
    if "어순" in (rule_type or ""):                          # 어순 규칙: 같은 단어들의 재배열이면 통과 (관사는 넣거나 뺄 수 있음)
        strip = lambda ts: sorted(t for t in ts if t not in _ARTICLES)
        if len(w) >= 2 and strip(w) == strip(f) and w != f:
            return None
        # 재배열이 아니어도 바로 거절하지 않는다 — 모델이 어순 규칙을 골라 놓고 read→red 처럼 한 단어를 고치기도 한다.
        # 규칙이 맞는지는 모델 몫, 서버 검증은 '학생이 안 쓴 문장을 지어냈나' 만 막는다 → 아래 일반 검사로 넘긴다
    if len(w) > 4:
        return f"wrong 이 너무 김 (4단어 초과): {wrong!r}"
    content_w = [t for t in w if t not in _FUNC_WORDS]
    if any(t in _TIME_WORDS for t in content_w):
        return f"wrong={wrong!r} 은 시간 표현 (규칙이 바꾸는 대상이 아님 — 어순 변경 시도)"
    for t in content_w:                                      # 학생의 내용어는 fix 에 (그대로든 변형이든) 남아 있어야 한다
        if not any(_related(t, x) for x in f):
            return f"fix={fix!r} 에 wrong 의 {t!r} 가 없음 (다른 단어로 교체)"
    extra = [x for x in f if not any(_related(x, t) for t in w)]
    new_content = [x for x in extra if x not in _FUNC_WORDS]
    if new_content:
        return f"fix={fix!r} 에 학생이 안 쓴 단어 {new_content} (관사·be동사·전치사만 덧붙일 수 있음)"
    others = _tokens(text)
    for t in w:
        if t in others:
            others.remove(t)
    pulled = [x for x in f if x not in _FUNC_WORDS and x not in w and not any(_related(x, t) for t in w) and x in others]
    if pulled:                                               # fix 가 문장 다른 곳에 이미 있는 단어 → 어순 바꾸기 시도 (yesterday→saw)
        return f"fix={fix!r} 가 문장에 이미 있는 단어 {pulled} (어순 변경 시도)"
    return None


_SPELL_VOCAB: set[str] = set()   # 교재 단어 (words·patterns·규칙 예문). 후보가 여럿이면 이걸 우선
_SPELL = None   # pyspellchecker (영어 단어 30만 + 빈도). 없으면 False — 철자 사전검사만 꺼지고 나머지는 그대로


def _spell():
    """영어 사전을 한 번만 만든다. 교재 단어(words·patterns·규칙 예문, ~950개)를 빈도 높게 얹어 후보에서 우선되게 한다."""
    global _SPELL
    if _SPELL is None:
        try:
            from spellchecker import SpellChecker
            sp = SpellChecker(distance=2)
            _SPELL_VOCAB.update(t.lower() for v in golden.known_english_vocab(None) for t in re.findall(r"[A-Za-z']+", v))
            sp.word_frequency.load_words(list(_SPELL_VOCAB) * 50)
            _SPELL = sp
        except ImportError:
            print("[fix] pyspellchecker 없음 → 철자 사전검사 생략 (pip install pyspellchecker)", flush=True)
            _SPELL = False
    return _SPELL or None


def _spell_precheck(text: str) -> list[dict]:
    """모델을 부르기 전에 사전으로 철자 실수를 찾는다 → [{"wrong","fix"}]. 사전에 있는 단어는 절대 안 건드린다 (drank, girls 보호).
    - 문장 중간의 대문자 단어(이름 Tom, Jane)와 두 글자 이하는 제외
    - 후보는 사전의 가장 가까운 단어이되 _is_typo(글자 1~3개 차이, 어형 변화 아님) 를 통과해야 함"""
    sp = _spell()
    if not sp:
        return []
    out = []
    for m in re.finditer(r"[A-Za-z']+", text):
        w = m.group(); lw = w.lower()
        if len(lw) < 3 or "'" in lw or (w[0].isupper() and m.start() > 0):
            continue
        if sp.known([lw]):
            continue
        allowed = 3 if len(lw) >= 7 else 2
        pool = set(sp.candidates(lw) or set()) | {v for v in _SPELL_VOCAB if abs(len(v) - len(lw)) <= allowed and _edit_distance(lw, v) <= allowed}
        pool.discard(lw)
        scored = []
        for c in pool:                                       # 점수 = 글자 차이 (교재 단어는 1 깎아 줌) → 같으면 사전 빈도 높은 것
            d = _edit_distance(lw, c)                        # aple→apple(교재) > able, elefant→elephant(교재) > elegant, becouse→because(빈도) > become
            if d <= allowed:
                scored.append((d - (1 if c in _SPELL_VOCAB else 0), -sp.word_frequency[c], c))
        cand = min(scored)[2] if scored else None
        if not cand or cand == lw or not _is_typo(lw, cand):
            continue
        out.append({"wrong": w, "fix": cand})
    return out


def _apply_spelling(text: str, pairs: list[dict]) -> str:
    """사전검사로 찾은 철자를 원문에 반영한 문장 (첫 글자 대문자는 유지). 이 문장을 검색·모델에 넘긴다."""
    for p in pairs:
        fix = p["fix"][0].upper() + p["fix"][1:] if p["wrong"][0].isupper() else p["fix"]
        text = re.sub(r"(?<![A-Za-z])" + re.escape(p["wrong"]) + r"(?![A-Za-z])", fix, text, count=1)
    return text


_SWAP_WORDS = _FUNC_WORDS | {"this", "these", "that", "those"}


def _second_opinion(text: str, fixed: str, backend: str | None, fallback: bool | None, timing: dict | None = None) -> bool:
    """be동사·관사 같은 기능어 한 개를 바꾼 답은 소형 모델이 맞는 문장도 뒤집는 경우가 잦다 ('My family is good' → are → 다시 is).
    원문과 고친 문장을 나란히 주고 어느 쪽이 맞는지 한 번 더 묻는다. True = 고친 문장(B)이 맞다고 확인됨 (모델 교정 유지).
    A 또는 both 면 False → 호출부가 원문을 맞는 문장(ok)으로 둔다. LLM 호출 자체가 실패하면 True (기존 답 유지)."""
    prompt = ("두 영어 문장 중 문법에 맞는 것을 고르세요. 초등 영어 기준. 둘 다 맞으면 both. 다른 말 없이 JSON 만: "
              '{"answer": "A" 또는 "B" 또는 "both"}' + "\n" + f"A: {text}" + "\n" + f"B: {fixed}")
    try:
        out = _ask_llm(prompt, backend, fallback, timing)
    except llm.LLMError:
        return True
    ans = str(out.get("answer", "")).strip().upper()
    return ans not in ("A", "BOTH")


def _spelling_pairs(text: str, full_fixed: str) -> list[dict]:
    """ok=true 인데 모델이 full_fixed 에 철자만 고쳐 준 경우 (read→red, dreass→dress) 그 쌍을 뽑는다.
    단어 수가 같고, 다른 단어가 전부 철자 쌍(_is_typo) 일 때만 인정. 단어가 늘거나 어형 변화·딴 단어로 바뀌었으면 [] (철자 아님 → 원문 유지)."""
    src, dst = _tokens(text), _tokens(full_fixed)
    if not dst or len(src) != len(dst):
        return []
    diff = [(a, b) for a, b in zip(src, dst) if a != b]
    if not diff or not all(_is_typo(a, b) for a, b in diff):
        return []
    return [{"wrong": a, "fix": b} for a, b in diff]


def _is_typo(a: str, b: str) -> bool:
    """철자 실수로 볼 수 있는 쌍인가: 글자 1~2개(7글자 이상은 3개) 차이이고, 기능어 교체나 어형 변화(go→went, cat→cats, eat→eating)는 아님."""
    if a in _FUNC_WORDS or b in _FUNC_WORDS:                # am→is, a→an 같은 문법 교체는 철자가 아님
        return False
    if b in _IRREGULAR.get(a, set()) or a in _IRREGULAR.get(b, set()):
        return False
    for suf in ("s", "es", "ed", "d", "ing", "ly", "er", "est"):
        if b == a + suf or a == b + suf:
            return False
    return _edit_distance(a, b) <= (3 if len(b) >= 7 else 2)   # 짧은 단어 2글자, 7글자 이상은 3글자 (vegetibals→vegetables)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein: 글자를 넣고·빼고·바꿔서 a 를 b 로 만드는 최소 횟수."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _student_words_only(text: str, fixed: str) -> str | None:
    """규칙 밖(OTHER) 답 검증. 고친 문장이 학생 단어(와 그 변형 go→went) + 기능어(관사·be동사·전치사)만으로 되어 있고,
    원문과 다르며, 2단어 넘게 길어지지 않았으면 None, 아니면 이유. 단어를 지우는 건 허용(went to go to → went to), 새 내용어는 거절."""
    src, dst = _tokens(text), _tokens(fixed)
    if not dst:
        return "고친 문장이 비어 있음"
    if dst == src:
        return "고친 문장이 원문과 같음"
    new_words = [t for t in dst if t not in src and t not in _FUNC_WORDS and not any(_related(t, w) for w in src)]
    if new_words:
        return f"학생이 안 쓴 단어 {new_words}"
    if len(dst) > len(src) + 2:
        return "문장이 너무 길어짐"
    return None


def _full_fixed_ok(text: str, full_fixed: str, fix: str | None) -> bool:
    """full_fixed 가 학생 문장에서 크게 벗어나지 않았는지 (느슨한 검사). 관사·fix 단어 외에 새 단어가 2개 넘게 들어오거나 문장이 2단어 넘게 길어지면 거부."""
    src, dst = _tokens(text), _tokens(full_fixed)
    if not dst:
        return False
    allowed = set(src) | _ARTICLES | set(_tokens(fix or ""))
    new_words = [t for t in dst if t not in allowed]
    return len(new_words) <= 2 and len(dst) <= len(src) + 2


def _search_candidates(text: str, k: int) -> tuple[list[dict], str, str | None]:
    """RAG 검색 (rag.py 의 search_rules, RAG 담당). 반환: (후보 목록, mode, fallback_reason). 호출부는 k=규칙 전부.
    후보는 score 내림차순이되, rag.py 의 어휘 안전망(R-01)이 걸리면 그 규칙이 순서와 무관하게 뒤에 붙을 수 있다 (k=전체면 해당 없음).
    - 검색 성공 → ([{id,type,text,unit,score}, …], "rag", None)
    - 색인 없음·임베딩/질의 실패(indexing.IndexUnavailableError) 나 그 외 예외 → ([], "fallback", "search_error")
    - 결과 0건 → ([], "fallback", "no_results")
    threshold 는 아직 안 건다: 실측에서 정상 문장이 오류 문장보다 점수가 높게 나와(0.415 vs 0.317) 점수로 정오를 가르면 역효과.
    정오 판단은 프롬프트·생성 모델의 ok 가 맡고, 검색은 '근거를 좁히는' 역할만 한다 (docs/RAG_0909/팀장-인계문서.md 3절)."""
    try:
        from backend import indexing
        from backend.rag import search_rules
    except ImportError as e:                                # rag.py/indexing.py 가 없는 환경
        print(f"[fix] 검색 모듈 없음 → 폴백: {e}", flush=True)
        return [], "fallback", "search_error"
    try:
        cands = search_rules(text, k=k)
    except indexing.IndexUnavailableError as e:
        print(f"[fix] 검색 불가 → 폴백: {e}", flush=True)
        return [], "fallback", "search_error"
    except Exception as e:                                   # 예상 밖 예외도 서비스는 살린다
        print(f"[fix] 검색 예외 → 폴백: {type(e).__name__}: {e}", flush=True)
        return [], "fallback", "search_error"
    if not cands:
        return [], "fallback", "no_results"
    return cands, "rag", None


# ─────────────────────────────────────────────
# 학생 DB (PRD 5.2)
# ─────────────────────────────────────────────
def _log_failure(orig: str, student: str, level: int, unit: str, source_kind: str, reason: str, record: bool, llm_info: dict | None = None) -> None:
    """검증 실패로 502 를 돌려주는 문장도 로그에 남긴다 (rule_id 없음, failed=이유). 규칙이 없어서 못 고친 문장 = 데이터팀이 규칙을 보탤 재료."""
    if not record:
        return
    _log_sentence({
        "log_id": "L-" + datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3], "ts": datetime.now().isoformat(timespec="seconds"),
        "student": student, "level": level, "unit": unit, "text": orig, "source": source_kind,
        "rule_id": None, "ok": None, "fixed": None, "failed": reason[:200], "mode": None,
        "llm": (llm_info or {}).get("backend"), "llm_ms": (llm_info or {}).get("ms"),
    })


def _log_sentence(row: dict) -> None:
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, (STUDENT_DIR / "sentence_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _notebook_add(student: str, rule_id: str, log_id: str) -> None:
    """notebook.json  {"A":{"R-01":{"count":3,"last":"2026-09-10","streak":0,"log_ids":[...]}}}"""
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    path = STUDENT_DIR / "notebook.json"
    with _lock:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = data.setdefault(student, {}).setdefault(rule_id, {"count": 0, "last": "", "streak": 0, "log_ids": []})
        entry["count"] += 1
        entry["last"] = datetime.now().strftime("%Y-%m-%d")
        entry["streak"] = 0                       # 또 틀렸으니 극복 진행 초기화
        entry["log_ids"] = (entry["log_ids"] + [log_id])[-10:]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
class FixIn(BaseModel):
    student: str = "A"
    level: int = 2
    unit: str = ""
    text: str
    source: str = "typed"           # "stt" | "typed"


_STOP = {"i", "a", "an", "the", "to", "at", "in", "on", "of", "and", "is", "am", "are", "was", "were", "it", "my", "you", "he", "she", "we", "they", "this", "that"}


def _suggest_questions(rule: dict | None, text: str) -> list[str]:
    """더 물어보기 칩. 원칙: /ask 가 답할 수 있고(FAQ·규칙 조각 안) **방금 문장과 관련 있는** 것만. 둘 다 아니면 비워 둔다.
    1) 틀린 규칙에 연결된 FAQ  2) 학생 문장의 단어가 들어 있는 FAQ (question·variants 의 영어 단어와 겹침, 예문은 제외)
    3) 틀렸으면 "규칙명 예문 더 보여줘" (규칙 조각으로 답 가능). Unit 공통 질문으로 채우지 않는다 — 문장과 무관한 칩은 신뢰를 깎는다."""
    faqs = golden.faqs()
    words = {w for w in _tokens(text) if len(w) >= 3 and w not in _STOP}
    out: list[str] = []
    if rule:
        out += [f["question"] for f in faqs if rule["id"] in (f.get("rule_ids") or [])]
    scored = []
    for f in faqs:
        if f["question"] in out:
            continue
        bag = {w for w in _tokens(" ".join([f.get("question", "")] + list(f.get("variants") or []))) if len(w) >= 3}   # 질문·변형에 나온 단어만 (예문은 제외 — zoo 같은 부수 단어로 엉뚱한 FAQ 가 걸림)
        hit = len(words & bag)
        if hit:
            scored.append((hit, f["question"]))
    out += [q for _, q in sorted(scored, key=lambda x: -x[0])]
    out = out[:2]
    if rule:
        out.append(f"{rule['type']} 예문 더 보여줘")
    return out[:3]


def diagnose(text: str, level: int = 3, unit: str = "", student: str = "A", source_kind: str = "typed", record: bool = True,
             backend: str | None = None, fallback: bool | None = None) -> dict:
    """/fix 의 본체. record=False 면 sentence_log·notebook 에 아무것도 쓰지 않는다 (RAG 담당 생성 평가용 → fix_internal)."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text 가 비어 있음")
    orig = text                                              # 학생이 쓴 그대로 (화면·로그용)
    pre_spelling = _spell_precheck(text)                     # 사전으로 먼저 잡은 철자 (모델과 무관)
    if pre_spelling:
        text = _apply_spelling(text, pre_spelling)           # 검색·모델·검증은 철자 고친 문장으로 (모델이 철자에 헤매지 않게)
        print(f"[fix] 철자 사전검사: {[(p['wrong'], p['fix']) for p in pre_spelling]} → {text!r}", flush=True)
    all_rules = golden.rules()
    if not all_rules:
        raise HTTPException(503, "rules.jsonl 이 없음 (data/golden/ 또는 _sample-B/)")
    unit_row = golden.find_unit(level, unit) or {}

    # 1) 검색은 규칙 전부를 받아 둔다 (점수·순위 표시용, 38개라 비용 없음). 프롬프트엔 상위 RAG_TOP_K + Unit 규칙 + 공통 규칙 (규칙이 RAG_ALL_IF_LE 이하면 전부)
    #    + 가짜 규칙 SPELL·OTHER. 검색 실패면 규칙 전부 (폴백)
    t_start = time.perf_counter()
    cands, mode, fallback_reason = _search_candidates(text, k=len(all_rules))
    timing = {"search_ms": int((time.perf_counter() - t_start) * 1000), "llm_ms": 0, "llm_calls": 0, "total_ms": 0}   # 단계별 시간 (로그·관리자용)
    if mode == "rag":
        if len(cands) != len(all_rules):                    # 색인이 rules.jsonl 과 다름 (데이터 갱신 뒤 --rebuild 안 함)
            print(f"[fix] 경고: 색인 {len(cands)}개 ≠ rules.jsonl {len(all_rules)}개 → python -m backend.indexing --rebuild 필요", flush=True)
        extra_ids = set(unit_row.get("rule_ids") or []) | {r["id"] for r in all_rules if r.get("unit") == "ALL"}
        if len(all_rules) <= RAG_ALL_IF_LE:
            prompt_rules = list(cands)
        else:
            prompt_rules = cands[:RAG_TOP_K] + [c for c in cands[RAG_TOP_K:] if c["id"] in extra_ids]
        seen = {r["id"] for r in prompt_rules}              # 색인에 없는 Unit·공통 규칙은 rules.jsonl 에서 보충
        prompt_rules += [r for r in all_rules if r["id"] in extra_ids and r["id"] not in seen]
    else:
        prompt_rules = all_rules
    prompt_rules = list(prompt_rules) + [SPELLING_RULE, OTHER_RULE]
    allowed_ids = {r["id"] for r in prompt_rules}          # 모델이 고를 수 있는 규칙 = 실제로 전달한 것만 (SPELL·OTHER 포함)

    prompt = _render(
        PROMPT_FILE.read_text(encoding="utf-8"),
        mission=unit_row.get("mission") or "(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words=", ".join(unit_row.get("hint_words") or []) or "(없음)",
        all_rules=_rules_block(prompt_rules),
        sentence=text,
    )
    shown = [(c["id"], round(c["score"], 3)) for c in cands[:RAG_TOP_K]] if cands else [r["id"] for r in all_rules]
    extra = [r["id"] for r in prompt_rules[RAG_TOP_K:] if r["id"] not in (SPELLING_RULE["id"], OTHER_RULE["id"])] if cands else []
    print(f"[fix] student={student} unit={unit} mode={mode}{' (' + fallback_reason + ')' if fallback_reason else ''} candidates={shown} +추가규칙={extra} text={text!r}", flush=True)

    # 2) 생성 → 3) 검증. 검증에 걸리면 이유를 덧붙여 한 번 더 생성, 그래도 안 되면 full_fixed 가 학생 단어뿐일 때 규칙 밖(OTHER)으로 살리고 아니면 502
    problem = None
    for attempt in (1, 2):
        sent = prompt if attempt == 1 else prompt + f"\n\n## 다시: 직전 답이 규칙 위반이었다 ({problem}). wrong 은 학생 문장에 실제로 있는 말(보통 한 단어, 어순 규칙이면 구간 전체), fix 는 그 말을 규칙에 맞게 바꾼 것만 쓴다. 학생이 안 쓴 단어를 넣거나 시간 표현을 바꾸지 않는다."
        if settings.log_prompt:                                  # 모델에 실제로 보내는 프롬프트 전문 (LOG_PROMPT=0 으로 끔)
            print(f"[fix] ── 프롬프트 ({attempt}차, {len(sent)}자, 규칙 {len(prompt_rules)}개) ──\n{sent}\n[fix] ── 프롬프트 끝 ──", flush=True)
        try:
            out = _ask_llm(sent, backend, fallback, timing)
        except llm.LLMError as e:                            # 할당량·네트워크·JSON 파싱
            raise HTTPException(502, str(e))
        llm_info = out.pop("_llm", {})
        print(f"[fix] {llm_info.get('backend')}:{llm_info.get('model')} {llm_info.get('ms')}ms 응답: {json.dumps(out, ensure_ascii=False)}", flush=True)

        ok = bool(out.get("ok"))
        _n = lambda x: re.sub(r"[.!?\s]+$", "", str(x or "")).strip().lower()
        nochange = not ok and ((out.get("wrong") or "").strip() == (out.get("fix") or "").strip() or _n(out.get("fixed")) == _n(text))
        if nochange and attempt == 1:                        # 고친 게 없는 답(hate→hate). 한 번은 다시 시킨다 — 'I drew zoo yesterday' 처럼 진짜 틀린 곳을 놓친 걸 수도
            problem = ("wrong 과 fix 가 같아서 고친 게 없음. 참고 규칙을 하나씩 문장에 대조해 보라 — 특히 관사(a/an 빠짐), 복수형(-s), 시제, be동사. "
                       "정말 고칠 곳이 없으면 ok=true 로, 있으면 실제로 바뀐 단어를 fix 에")
            print(f"[fix] 검증 실패(1차): {problem}", flush=True)
            continue
        if nochange:                                         # 2차도 고친 게 없으면 사실상 문법 OK (소형 모델이 '틀린 곳을 꼭 골라야' 한다고 여김)
            print(f"[fix] 2차도 고친 게 없음 (wrong={out.get('wrong')!r}) → 맞는 문장으로 처리", flush=True)
            ok = True
        rule_id = (out.get("rule_id") or "").strip() if not ok else ""
        if not ok and rule_id not in allowed_ids:            # 근거 밖 규칙 (전체 목록 기준이 아니라 '전달한 근거' 기준 — 인계문서 4번)
            problem = f"근거 밖 규칙 id={rule_id or '없음'} (전달한 근거: {sorted(allowed_ids)})"
        elif not ok and rule_id == OTHER_RULE["id"]:         # 규칙 밖 → (wrong,fix) 대신 full_fixed 가 학생 단어로만 된 다른 문장인지
            reason = _student_words_only(text, (out.get("full_fixed") or out.get("fixed") or "").strip())
            problem = None if reason is None else f"규칙 밖 답인데 {reason}"
        elif not ok:
            rt = (golden.find_rule(rule_id) or {}).get("type", "")
            problem = _pair_problem(text, out.get("wrong"), out.get("fix"), rt)
        else:
            problem = None
        if problem is None:
            break
        print(f"[fix] 검증 실패({attempt}차): {problem}", flush=True)
    if problem is not None:
        salvage = (out.get("full_fixed") or "").strip()
        if not ok and salvage and _student_words_only(text, salvage) is None:   # 규칙은 잘못 짚었지만 문장 제안은 학생 단어뿐 → 규칙 밖으로 살림
            print(f"[fix] 검증 2회 실패 → 규칙 밖으로 전환 (full_fixed={salvage!r})", flush=True)
            rule_id, problem = OTHER_RULE["id"], None
            out["wrong"] = out["fix"] = None
            out["why"] = "우리 교과서 규칙으로는 짚기 어려운 부분이에요. 이렇게 말하면 자연스러워요."   # 잘못 짚은 규칙의 설명은 버린다
        else:
            _log_failure(orig, student, level, unit, source_kind, problem, record, llm_info)
            raise HTTPException(502, f"모델 답이 규칙에 안 맞아 버렸어요 ({problem}). 다시 [고쳐줘]를 눌러 주세요.")
    other = (not ok) and rule_id == OTHER_RULE["id"]
    typo_pair = None
    if not ok:                                               # 모델이 철자 실수(read→red)를 문법 규칙(어순 등)으로 잡는 경우 — 프롬프트 1-1 을 소형 모델이 자주 무시함
        wt, ft = _tokens(out.get("wrong") or ""), _tokens(out.get("fix") or "")
        if len(wt) == 1 and len(ft) == 1 and (rule_id == SPELLING_RULE["id"] or _is_typo(wt[0], ft[0])):
            typo_pair = (wt[0], ft[0])
            print(f"[fix] 철자({wt[0]}→{ft[0]}) — 규칙 {rule_id} → 문법 ok 로 전환, 철자만 안내", flush=True)
            ok = True
        elif rule_id == SPELLING_RULE["id"]:                 # 철자 규칙인데 한 단어 쌍이 아니면 답으로 못 씀
            _log_failure(orig, student, level, unit, source_kind, f"철자 규칙인데 단어 쌍 아님 {out.get('wrong')!r}→{out.get('fix')!r}", record, llm_info)
            raise HTTPException(502, f"모델이 철자 규칙을 골랐지만 단어 쌍이 아님 ({out.get('wrong')!r}→{out.get('fix')!r}). 다시 [고쳐줘]를 눌러 주세요.")
    if not ok and not other:                                 # 기능어 한 개 바꾼 답(is→are, a→an)은 한 번 더 확인 — 맞는 문장을 뒤집는 오교정 방지
        wt, ft = _tokens(out.get("wrong") or ""), _tokens(out.get("fix") or "")
        if len(wt) == 1 and len(ft) == 1 and wt[0] in _SWAP_WORDS and ft[0] in _SWAP_WORDS:
            cand = _single_fix(text, out.get("wrong"), out.get("fix")) or (out.get("fixed") or "")
            if not _second_opinion(text, cand, backend, fallback, timing):
                print(f"[fix] 재확인: {wt[0]}→{ft[0]} 고침이 더 맞다고 못 함 → 원문 유지(ok)", flush=True)
                ok = True
    rule = golden.find_rule(rule_id) if not ok else None

    raw_fixed = (out.get("fixed") or text).strip()
    fixed = raw_fixed
    single = _single_fix(text, out.get("wrong"), out.get("fix")) if not ok else None
    norm = lambda x: re.sub(r"[.!?\s]+$", "", x).strip().lower()          # 끝 문장부호·대소문자 차이는 "여러 곳 고침" 으로 보지 않는다
    if single and norm(single) != norm(fixed):
        print(f"[fix] 모델이 여러 곳을 고침 → 1위 규칙만 반영: {fixed!r} → {single!r}", flush=True)
    if single:
        fixed = single                                       # 표기(첫 글자 대문자·마침표)는 항상 서버 기준으로 통일
        if _broken(single) and not _broken(raw_fixed) and _student_words_only(text, raw_fixed) is None:
            fixed = _tidy(raw_fixed)                         # 모델이 wrong 범위를 한 단어 짧게 잡아('go to go'→'go to') 겹말이 생기면 모델 문장을 쓴다
            print(f"[fix] 한 곳만 바꾼 문장에 겹말 → 모델 문장 사용: {single!r} → {fixed!r}", flush=True)
    full_fixed = (out.get("full_fixed") or "").strip() or fixed
    if other:                                                # 규칙 밖: 고친 문장 하나뿐. 표기(첫 글자·마침표)는 _single_fix 와 같은 기준으로
        fixed = full_fixed = _tidy(full_fixed)
    if not ok and not other and not _full_fixed_ok(text, full_fixed, out.get("fix")):   # 학생이 안 쓴 내용을 덧붙인 문장('to the zoo and …')은 버린다
        print(f"[fix] full_fixed 에 새 내용이 들어가 버림: {full_fixed!r} → {fixed!r}", flush=True)
        full_fixed = fixed
    spelling = _spelling_pairs(orig, full_fixed) if ok else list(pre_spelling)   # ok: 원문 대비 철자 전부(사전검사+모델). 아니면 사전검사분만
    if ok and typo_pair and not spelling:                    # 모델의 full_fixed 에 다른 것도 섞여 있으면 (wrong→fix) 한 쌍만 반영
        full_fixed = _single_fix(text, typo_pair[0], typo_pair[1]) or text
        spelling = _spelling_pairs(orig, full_fixed)
    timing["total_ms"] = int((time.perf_counter() - t_start) * 1000)
    log_id = "L-" + datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    mission = out.get("mission") if isinstance(out.get("mission"), dict) else {"ok": True, "nudge": ""}

    # 4) 근거·점수는 모델이 아니라 '서버가 전달한 후보' 에서 구성 (인계문서 2절)
    top = cands[0] if cands else None
    chosen = next((c for c in cands if rule and c["id"] == rule["id"]), None)          # 모델이 고른 규칙의 검색 후보
    second = next((c for c in cands if chosen and c["id"] != chosen["id"]), None)      # 그 외 후보 중 최고 점수
    if rule and mode == "rag" and chosen:
        rule_field = {"id": chosen["id"], "name": chosen["type"], "score": round(chosen["score"], 4), "rank": cands.index(chosen) + 1}
        source = {"chunk_id": chosen["id"], "text": chosen["text"]}
    elif rule:
        rule_field = {"id": rule["id"], "name": rule["type"], "score": None}
        source = {"chunk_id": rule["id"], "text": rule["text"]}
    elif other:
        rule_field, source = {"id": OTHER_RULE["id"], "name": OTHER_RULE["type"], "score": None}, None
    else:
        rule_field, source = None, None
    runner_up = {"id": second["id"], "name": second["type"], "score": round(second["score"], 4), "rank": cands.index(second) + 1} if (rule and second and mode == "rag") else None   # 모델이 고른 것 외 최고 후보 (rank 는 검색 순위 — 모델이 22위를 골랐으면 이게 1위일 수 있음). ok 면 null

    result = {
        "ok": ok,
        "rule": rule_field,
        "runner_up": runner_up,
        "wrong": None if ok else out.get("wrong"),
        "fix": None if ok else out.get("fix"),
        "fixed": orig if ok else fixed,
        "why": "문법에 맞는 문장이에요. 다른 문장도 말해볼까요?" if ok else (out.get("why") or ""),   # 맞는 문장이면 고정 문구 — 모델이 미션 지적을 why 에 섞는 것 방지 (미션은 mission.nudge 로만)
        "source": source,
        "more_errors": bool(out.get("more_errors")) and not ok and not other,
        "full_fixed": (full_fixed if spelling else orig) if ok else full_fixed,   # 다 고친 문장. ok 면 철자만 고친 문장(없으면 원문)
        "spelling": spelling,                                  # ok 인데 철자만 틀린 경우 [{"wrong","fix"}] — 화면 "철자만 살짝" 한 줄용
        "suggested_questions": _suggest_questions(rule, text),   # FAQ 에서 고름 (모델이 지어낸 질문은 /ask 가 못 답함)
        "mission": {"ok": bool(mission.get("ok", True)), "nudge": mission.get("nudge") or ""},
        "log_id": log_id,
        "mode": mode,
        "fallback_reason": fallback_reason,                    # "search_error" | "no_results" | None
        "candidates": [{"id": c["id"], "name": c["type"], "score": round(c["score"], 4)} for c in cands[:RAG_TOP_K]],   # 검색 상위 RAG_TOP_K (관리자·실험용)
        "llm": llm_info,                                       # {"backend","model","ms","fallback_from"} — 비교 실험·관리자용
        "timing": timing,                                      # {"search_ms","llm_ms","llm_calls","total_ms"} — 발표용 근거 박스·로그
    }

    if record:
        _log_sentence({
            "log_id": log_id, "ts": datetime.now().isoformat(timespec="seconds"), "student": student,
            "level": level, "unit": unit, "text": orig, "source": source_kind,
            "spelled": text if pre_spelling else None,        # 사전검사로 철자 고친 뒤 실제로 진단한 문장
            "rule_id": rule["id"] if rule else None, "ok": ok, "fixed": result["fixed"],
            "mission_ok": result["mission"]["ok"], "mode": mode, "fallback_reason": fallback_reason,
            "top_score": round(top["score"], 4) if top else None,
            "llm": llm_info.get("backend"), "llm_ms": llm_info.get("ms"),
            "total_ms": timing["total_ms"], "search_ms": timing["search_ms"], "llm_calls": timing["llm_calls"],
        })
        if rule:
            _notebook_add(student, rule["id"], log_id)
    print(f"[fix] 시간: 전체 {timing['total_ms']}ms = 검색 {timing['search_ms']}ms + 모델 {timing['llm_ms']}ms ({timing['llm_calls']}회) + 나머지", flush=True)
    print(f"[fix] 결과: ok={ok} rule={rule['id'] if rule else None} mode={mode} fixed={result['fixed']!r} more_errors={result['more_errors']} "
          f"mission_ok={result['mission']['ok']} log_id={log_id}{'' if record else ' (기록 안 함)'}", flush=True)
    return result


def fix_internal(text: str, level: int = 3, unit: str = "", backend: str | None = None, fallback: bool | None = None) -> dict:
    """POST /fix 와 같은 로직이되 sentence_log·notebook 에 기록하지 않는다. 반환 형식은 /fix 응답과 동일.
    tests/eval_fix.py(모델·조건 비교)가 쓴다. RAG 담당의 생성 평가(eval_rag --with-generation, 예정)도 이걸 부르면 된다. HTTPException 은 그대로 올라간다."""
    return diagnose(text, level=level, unit=unit, student="EVAL", source_kind="eval", record=False, backend=backend, fallback=fallback)


@router.post("/fix")
def fix(body: FixIn):
    if not settings.has_api_key and (settings.llm_backend or "gemini") == "gemini":
        raise HTTPException(500, "GEMINI_API_KEY 가 설정되어 있지 않음")
    return diagnose(body.text, level=body.level, unit=body.unit, student=body.student, source_kind=body.source, record=True)
