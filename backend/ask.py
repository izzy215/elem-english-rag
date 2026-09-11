"""
물어보기 챗 (PRD 4.4, 화면/통합은 팀장 소관 · 백엔드가 아직 없어서 TTS 담당이 임시로 준비)

POST /api/ask
body: {"student", "question", "context": {"screen","unit","rule_id","log_id"}}
→ {"answer", "source": [{"chunk_id"}], "offtopic", "suggested": [...]}
(common.js 의 askChat() 이 이미 이 형식을 기다림 — 필드 바꾸면 그쪽도 같이 바꿔야 함)

1) 로컬 매칭(faq.jsonl→rules.jsonl 단어 겹침) 먼저 — 되면 LLM 호출 없이 즉시 반환
2) 안 되면 backend/llm.py 로 폴백(faq 전체를 프롬프트에 넣고 고르게 함 — Gemini 기본, .env
   LLM_BACKEND=local 이면 강의실 서버 로컬 모델. rag.search 완성되면 1위 조각만 넣게 바꿀 수 있음)

context.log_id 가 있으면 sentence_log.jsonl 에서 그 순간의 원문·고친 문장을 찾아 프롬프트에
넣는다("아까 말한 거 고쳐줘"에 다시 추론 안 하고 /fix 결과를 그대로 씀). student.py 의
notebook_text() 도 개인화 참고 자료로 넣는다(답 근거는 여전히 FAQ).

매 질문·답변을 chat_log.jsonl 에 기록해뒀다가, 같은 학생이 CHAT_HISTORY_WINDOW_SEC 이내에
또 물어보면 최근 대화를 프롬프트에 같이 줘서 "그거/이거" 같은 지시어를 이해하게 한다
(프론트가 대화 기록을 안 보내도 서버가 student+시간 윈도우로 알아서 판단, 2026-09-10).
"""
import json
import re
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from backend import golden, llm
from backend.config import settings

router = APIRouter(tags=["ask"])
SENTENCE_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "sentence_log.jsonl"
CHAT_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "chat_log.jsonl"
CHAT_HISTORY_WINDOW_SEC = 180   # 이 안이면 "같은 대화"로 보고 그거/이거 지시어 힌트로 씀
CHAT_HISTORY_MAX_TURNS = 2


class AskContext(BaseModel):
    screen: str | None = None
    unit: str | None = None
    rule_id: str | None = None
    log_id: str | None = None


class AskIn(BaseModel):
    student: str = "A"
    question: str
    context: AskContext = AskContext()


def _norm_words(text: str) -> list[str]:
    return [w for w in re.sub(r"[?？.!,]", "", text.lower()).split() if w]


_GENERIC_WORDS = {"뭐예요", "뭐야", "무슨", "뜻이", "뜻이에요", "뜻인가요", "뜻이야"}


def _content_words(text: str) -> list[str]:
    """"무슨 뜻이에요"류 범용 의문 표현만 뺀 단어 목록 — 이것만 겹쳐서 서로 다른 단어를
    묻는 질문끼리 오매칭되는 걸 막는다(2026-09-10, "elephant 뜻이 뭐예요?"가 F-06(zoo)에
    잘못 매칭된 사례)."""
    return [w for w in _norm_words(text) if w not in _GENERIC_WORDS]


def _best_match(question: str, items: list[dict], candidates_of) -> tuple[dict | None, float]:
    """단어 겹침 기반 매칭. frontend/js/common.js 의 faqMatch()와 같은 알고리즘 —
    서버가 먼저 이걸로 찾아보고, 못 찾을 때만 Gemini 로 넘어간다(할당량 절약, 응답도 빠름)."""
    qs = _content_words(question)
    best, best_score = None, 0.0
    for item in items:
        for cand in candidates_of(item):
            cs = _content_words(cand)
            if not cs:
                continue
            # 부분 문자열 겹침은 두 단어 다 3글자 이상일 때만 인정 — 2글자는 "an"이 "elephant"의
            # 부분 문자열이라 무관한 단어끼리 겹치는 경우가 있음(2026-09-10). 완전히 같은 단어는 길이 상관없이 인정.
            hit = sum(1 for w in cs if any(w == x or (len(w) >= 3 and len(x) >= 3 and (w in x or x in w)) for x in qs))
            if len(cs) >= 2 and hit < 2:
                continue   # 단어 2개 이상인 후보가 1개만 겹치면 우연의 일치로 보고 스킵 — "과거형이 뭐에요?"가
                           # "see 과거형"과 "과거형" 한 단어만 겹쳐 saw 전용 FAQ로 잘못 매칭되던 문제(2026-09-10)
            score = hit / len(cs)
            if score > best_score:
                best_score, best = score, item
    return best, best_score


def _rag_hint_rule_id(question: str) -> tuple[str | None, float]:
    """질문과 가장 가까운 규칙 id·score(RAG 검색). 색인 없음 등 실패하면 (None, 0.0) — 게이트를 그냥 통과시킴."""
    try:
        from backend.rag import search_rules
        hits = search_rules(question, k=1)
        return (hits[0]["id"], hits[0]["score"]) if hits else (None, 0.0)
    except Exception:
        return (None, 0.0)


def _followup_questions(rule_ids: list[str], faq_list: list[dict], exclude_id: str | None = None) -> list[str]:
    """rule_ids 와 연결된 다른 FAQ 질문 최대 2개(방금 답한 FAQ 자신은 제외) — tutor.py 의
    _suggest_questions() 와 같은 목적, 로컬 매칭·정오 판정 답변도 항상 빈 채로 안 남게."""
    if not rule_ids:
        return []
    out = []
    for f in faq_list:
        if f.get("id") == exclude_id or not any(rid in rule_ids for rid in (f.get("rule_ids") or [])):
            continue
        out.append(f["question"])
        if len(out) >= 2:
            break
    return out


def _word_match(question: str, words_pool: dict[str, dict]) -> dict | None:
    """질문에 등장한 영단어가 words.csv(교재 어휘 전체, ~400개)에 정확히 있으면 그 뜻으로 답한다.
    FAQ에 없는 대다수 교재 단어(예: play)가 계속 offtopic 처리되던 걸 확인해서 추가(2026-09-10)."""
    for w in re.findall(r"[A-Za-z']+", question):
        entry = words_pool.get(w.lower())
        if entry:
            answer = f"{entry['word']}는 '{entry['meaning']}'라는 뜻이에요."
            if entry.get("example"):
                answer += f" 예: {entry['example']}"
            return {"answer": answer, "source": [], "offtopic": False, "suggested": []}
    return None


def _pattern_match(question: str, patterns_pool: list[dict], faq_list: list[dict]) -> dict | None:
    """질문 문장이 patterns.csv(교재 예문 전체)와 크게 겹치면 그 뜻으로 답한다(예: "Good night!")."""
    best, best_score = _best_match(question, patterns_pool, lambda p: [p["text"]])
    if best_score < 0.6:
        return None
    rule_ids = [best["rule_id"]] if best.get("rule_id") else []
    return {"answer": f"{best['text']}는 '{best['meaning']}'라는 뜻이에요.",
            "source": [{"chunk_id": rid} for rid in rule_ids], "offtopic": False,
            "suggested": _followup_questions(rule_ids, faq_list)}


def _local_match(question: str, faq_list: list[dict], rule_list: list[dict],
                  words_pool: dict[str, dict], patterns_pool: list[dict]) -> dict | None:
    """faq→rules→patterns→words 순으로 로컬 매칭. 전부 실패하거나 RAG 힌트와 어긋나면 None → 폴백."""
    rag_rule_id, rag_score = _rag_hint_rule_id(question)

    def _rag_disagrees(rule_ids: list[str]) -> bool:
        return bool(rule_ids) and rag_rule_id is not None and rag_score >= 0.5 and rag_rule_id not in rule_ids

    faq, faq_score = _best_match(question, faq_list, lambda f: [f["question"]] + (f.get("variants") or []))
    if faq_score >= 0.5:
        faq_rule_ids = faq.get("rule_ids") or []
        if not _rag_disagrees(faq_rule_ids):
            source = [{"chunk_id": rid} for rid in faq_rule_ids] + [{"chunk_id": faq["id"]}]
            suggested = _followup_questions(faq_rule_ids, faq_list, exclude_id=faq["id"])
            return {"answer": faq["answer"], "source": source, "offtopic": False, "suggested": suggested}
        print(f"[ask] 로컬 매칭 {faq['id']}(단어겹침 {faq_score:.2f}) 이 RAG 힌트({rag_rule_id}, {rag_score:.2f})와 어긋나 폴백으로 넘김", flush=True)

    rule, rule_score = _best_match(question, rule_list, lambda r: [r["type"], r.get("short", "")])
    if rule_score >= 0.5:
        if not _rag_disagrees([rule["id"]]):
            return {"answer": rule.get("short") or rule["text"], "source": [{"chunk_id": rule["id"]}],
                    "offtopic": False, "suggested": _followup_questions([rule["id"]], faq_list)}
        print(f"[ask] 로컬 매칭 {rule['id']}(단어겹침 {rule_score:.2f}) 이 RAG 힌트({rag_rule_id}, {rag_score:.2f})와 어긋나 폴백으로 넘김", flush=True)

    # 패턴(전체 문장) 매칭을 단어 매칭보다 먼저 본다 — "Good night!"가 그 안의 "night" 단어
    # 매칭에 먼저 걸려버리면 더 정확한 문장 전체 뜻 대신 단어 하나 뜻만 나오는 문제가 있었음(2026-09-10)
    pattern = _pattern_match(question, patterns_pool, faq_list)
    if pattern:
        return pattern

    return _word_match(question, words_pool)


def _log_entry(log_id: str) -> dict | None:
    """log_id로 sentence_log.jsonl(tutor.py 소유, 읽기만 함) 한 줄을 찾는다 —
    "아까 말한 거 고쳐줘"에 이미 계산된 원문/고친 문장/규칙을 그대로 쓰기 위함."""
    if not SENTENCE_LOG.exists():
        return None
    try:
        lines = SENTENCE_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("log_id") == log_id:
            return row
    return None


def _log_chat_turn(student: str, question: str, answer: str, source: list[dict] | None = None) -> None:
    """방금 질문·답변(+근거 규칙/FAQ id)을 기록 — 다음 질문의 "그거/이거"·"비슷한 거"가
    뭘 가리키는지 판단하는 재료(2026-09-10)."""
    if not question or not answer:
        return
    try:
        CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        chunk_ids = [s.get("chunk_id", "") for s in (source or [])]
        row = {
            "student": student, "question": question, "answer": answer, "ts": time.time(),
            "rule_ids": [c for c in chunk_ids if c.startswith("R-")],
            "faq_id": next((c for c in chunk_ids if c.startswith("F-")), None),
        }
        with CHAT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _recent_chat_turns(student: str, max_turns: int = CHAT_HISTORY_MAX_TURNS) -> list[dict]:
    """이 학생이 CHAT_HISTORY_WINDOW_SEC 이내에 나눈 최근 대화 최대 max_turns개."""
    if not CHAT_LOG.exists():
        return []
    now = time.time()
    turns = []
    try:
        lines = CHAT_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("student") != student:
            continue
        if now - row.get("ts", 0) > CHAT_HISTORY_WINDOW_SEC:
            break
        turns.append(row)
        if len(turns) >= max_turns:
            break
    return list(reversed(turns))


def _history_block(student: str) -> str:
    turns = _recent_chat_turns(student)
    if not turns:
        return ""
    lines = "\n".join(f'Q: {t["question"]}\nA: {t["answer"]}' for t in turns)
    return f"\n## 방금 나눈 대화\n{lines}\n"


_SIMILAR_PATTERN = re.compile(r"비슷한|다른\s*(거|것|게).{0,4}(있|알려|보여)|또\s*(없|있)|말고\s*또")


def _related_faq(rule_ids: list[str], faq_list: list[dict], exclude_ids: set[str]) -> dict | None:
    for f in faq_list:
        if f.get("id") in exclude_ids or not any(rid in rule_ids for rid in (f.get("rule_ids") or [])):
            continue
        return f
    return None


def _alternative_response(student: str, faq_list: list[dict]) -> dict | None:
    """방금 답의 근거 규칙(rule_ids)과 연결된 "다른" FAQ를 결정적으로 찾아 답한다. 근거 규칙이
    아예 없으면(순수 LLM 지식 답변 등) None. 대안 FAQ가 데이터에 없으면(38개 규칙 중 30개가
    이 상태, 2026-09-10 실측) LLM한테 넘기지 않고 정직하게 없다고 답한다."""
    # 직전 턴이 자유 설명(근거 규칙 없음)일 수 있어 조금 더 거슬러 올라가며 규칙이 있는 턴을 찾는다
    turns = _recent_chat_turns(student, max_turns=5)
    grounded = next((t for t in reversed(turns) if t.get("rule_ids")), None)
    if not grounded:
        return None
    rule_ids = grounded["rule_ids"]
    faq = _related_faq(rule_ids, faq_list, {grounded.get("faq_id") or ""})
    if faq:
        return {"answer": faq["answer"], "source": [{"chunk_id": faq["id"]}], "offtopic": False,
                "suggested": _followup_questions(rule_ids, faq_list, exclude_id=faq["id"])}
    rule = golden.find_rule(rule_ids[0])
    return {"answer": f'"{rule["type"]}"에 대해서는 방금 설명한 게 전부예요. 다른 게 궁금하면 물어봐!' if rule
            else "음, 지금은 비슷한 게 따로 없어. 다른 게 궁금하면 물어봐!",
            "source": [{"chunk_id": rule_ids[0]}], "offtopic": False, "suggested": []}


def _similar_match(question: str, student: str, faq_list: list[dict]) -> dict | None:
    """"비슷한 게 있을까요?" 류 요청을 정규식으로 미리 잡아 LLM 호출 없이 처리(빠른 경로).
    정규식이 못 잡는 표현은 LLM 폴백의 wants_more 필드가 대신 잡는다(_answer 참고)."""
    if not _SIMILAR_PATTERN.search(question):
        return None
    return _alternative_response(student, faq_list)


def _faq_block(faq_list: list[dict]) -> str:
    lines = []
    for f in faq_list:
        variants = ", ".join(f.get("variants") or [])
        rule_ids = ", ".join(f.get("rule_ids") or []) or "없음"
        lines.append(f"- [{f['id']}] Q: {f['question']} (비슷한 표현: {variants})\n  A: {f['answer']}  (근거 규칙: {rule_ids})")
    return "\n".join(lines)


PROMPT = """너는 초등학교 3~4학년에게 영어를 가르치는 다정한 선생님이다.
학생이 질문을 하면, 아래 "참고 FAQ" 목록 안에서 가장 비슷한 질문을 찾아 그 답을 참고해서 대답한다.

## 꼭 지킬 것
1. 답의 근거는 반드시 "참고 FAQ" 목록 안에 있어야 한다. 목록에 없는 내용은 답하지 않는다.
2. 목록 어디에도 관련된 게 없으면 offtopic=true 로, answer 는 "선생님한테 물어볼까?" 같은 부드러운 문장으로.
3. 답변은 한국어, 초등학생이 이해할 수 있게 2~3문장 이내.
4. "방금 학생이 만든 문장" 정보가 아래에 있고, 학생이 "아까 말한 거/그 문장 고쳐줘"처럼 그 문장을
   가리키는 요청을 하면, 새로 추론하지 말고 거기 적힌 "고친 문장"을 그대로 답에 써라.
5. "이 학생의 오답노트"는 답의 근거로 쓰지 않는다 — 어떤 걸 자주 틀리는지 알아서 설명 톤을 그
   학생에 맞게 조절하는 참고 자료일 뿐이다(예: 그 학생이 잘 틀리는 부분이면 조금 더 친절하게).
6. 학생 질문에 "그거/이거/왜 그래/그렇게" 같은 지시어가 있으면, 엉뚱한 새 FAQ를 찾지 말고 "방금
   나눈 대화"에서 마지막으로 다룬 내용을 이어서 답하라 — 그 대화 자체가 근거이니 FAQ에 안 나와도
   offtopic 처리하지 않는다(1번 규칙의 예외). 예: 방금 대화가 farewell 뜻이었고 학생이 "그거 예문
   보여줘"라 하면 farewell 예문으로, "왜 그래?"라 하면 그 설명을 더 풀어서 답한다.
7. 학생이 "그거 말고 다른 건?/비슷한 거 있어?/또 없어?"처럼 방금 다룬 것과 다른 걸 더 달라고
   하면 wants_more=true (표현이 뭐든 의도만 판단하면 됨 — answer는 평소처럼 채워도 되고, 실제
   답은 다른 로직이 대신 정할 수 있다).
8. 출력은 아래 JSON 하나만. 다른 말은 쓰지 않는다.

## 지금 상황
화면: {screen} · 유닛: {unit} · 방금 나온 규칙: {rule_id}
{log_block}{history_block}
## 이 학생의 오답노트 (참고용, 답 근거 아님)
{notebook_block}

## 참고 FAQ (이 안에서만 고른다)
{faq_block}

## 학생 질문
{question}

## 출력 JSON
{{
  "answer": "답변 2~3문장",
  "faq_id": "가장 근거가 된 FAQ id (예: F-01). 없으면 null",
  "offtopic": true 또는 false,
  "wants_more": true 또는 false,
  "suggested": ["이어서 물어볼 만한 짧은 질문 2개"]
}}"""


_CORRECTNESS_PATTERN = re.compile(
    r"맞는\s*문장|틀린\s*문장|맞습니까|"
    r"맞아|맞나|맞지|맞을까|틀렸어|틀렸나|틀렸지|틀려"
)   # "맞아요"뿐 아니라 "맞아?"처럼 요 없는 구어체도 잡음(2026-09-10)

_CORRECTNESS_FALLBACK = {
    "answer": "오, 그건 내가 여기서 바로 맞다 틀리다 봐주기는 어려워! "
              "'내 문장 말하기'에서 그 문장을 말하고 [고쳐줘]를 눌러보면 정확하게 확인해줄게 🙂",
    "source": [], "offtopic": False, "suggested": [],
}

CORRECTNESS_PROMPT = """너는 초등학교 3~4학년 영어 선생님이다. 학생이 문장이 맞는지 물어봤다.
아래 문법 규칙만 근거로 그 문장을 판정해라(목록에 없는 문법은 판단하지 않는다).

## 문법 규칙
{rules_block}

## 학생 질문
{question}

## 출력 JSON
{{
  "sentence": "질문 속 판정 대상 영어 문장 (없으면 빈 문자열)",
  "ok": true 또는 false,
  "rule_id": "틀렸으면 근거 규칙 id, 맞으면 null",
  "fixed": "틀렸으면 고친 문장, 맞으면 원문 그대로",
  "why": "1~2문장, 초등학생이 이해할 수 있게"
}}"""


def _check_correctness(question: str) -> dict:
    """"맞는 문장이에요?" 류 질문을 /fix 를 부르지 않고 자체 판정한다(sentence_log/notebook 에
    기록 안 남김 — 궁금해서 물어본 거지 "내 문장 말하기" 연습이 아니라서). 실패하면 안내 문구로
    폴백(호출부에서 처리)."""
    prompt = CORRECTNESS_PROMPT.format(rules_block="\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in golden.rules()), question=question)
    out = llm.generate_json(prompt)
    llm_info = out.pop("_llm", {})
    ok = bool(out.get("ok", True))
    rule = golden.find_rule(out.get("rule_id")) if not ok else None
    sentence = (out.get("sentence") or "").strip()
    if ok:
        answer = f'네, "{sentence}"는 맞는 문장이에요! 👍' if sentence else "네, 맞는 문장이에요!"
    else:
        answer = f'{(out.get("why") or "").strip()} "{out.get("fixed", "")}"가 맞아요.'.strip()
    suggested = _followup_questions([rule["id"]], golden.faqs()) if rule else []
    return {"answer": answer, "source": [{"chunk_id": rule["id"]}] if rule else [], "offtopic": False,
            "suggested": suggested, "llm": llm_info}


@router.post("/ask")
def ask(body: AskIn):
    result = _answer(body)
    _log_chat_turn(body.student, body.question.strip(), result.get("answer", ""), result.get("source"))
    return result


def _answer(body: AskIn) -> dict:
    question = body.question.strip()
    if not question:
        return {"answer": "", "source": [], "offtopic": True}

    if _CORRECTNESS_PATTERN.search(question):
        if not settings.has_api_key:
            return {"answer": "", "source": [], "offtopic": True, "error": "GEMINI_API_KEY 미설정"}
        try:
            return _check_correctness(question)
        except llm.LLMError:
            return _CORRECTNESS_FALLBACK

    all_faqs = golden.faqs()
    all_rules = golden.rules()
    if not all_faqs and not all_rules:
        return {"answer": "", "source": [], "offtopic": True, "error": "faq.jsonl/rules.jsonl 이 없음"}

    # "비슷한 거 있어?" 류는 LLM 자체 탐색이 신뢰도 낮아서(2026-09-10), 방금 답의 근거 규칙으로
    # 결정적으로 찾아본다 — 찾으면 즉시 반환, 못 찾으면(근거 규칙 없음 등) 아래 로컬 매칭으로 폴백
    similar = _similar_match(question, body.student, all_faqs)
    if similar is not None:
        return similar

    words_pool = {w["word"].lower(): w for w in golden.all_words()}
    patterns_pool = golden.all_patterns()

    # 1) 로컬 매칭 먼저 — faq/rules/words/patterns 안에서 바로 찾아지면 Gemini 호출 없이 즉시 반환
    local = _local_match(question, all_faqs, all_rules, words_pool, patterns_pool)
    if local is not None:
        return local

    # 2) 로컬 매칭 실패 → llm.py 폴백 (faq 전체를 프롬프트에 넣고 고르게 함)
    if not settings.has_api_key:
        return {"answer": "", "source": [], "offtopic": True, "error": "GEMINI_API_KEY 미설정"}

    ctx = body.context
    # rule_id가 있으면 관련 FAQ를 목록 앞쪽에 둬서 프롬프트에서 더 눈에 띄게 함
    if ctx.rule_id:
        all_faqs = sorted(all_faqs, key=lambda f: ctx.rule_id not in (f.get("rule_ids") or []))

    log = _log_entry(ctx.log_id) if ctx.log_id else None
    log_block = ""
    if log:
        log_block = (
            "\n## 방금 학생이 만든 문장\n"
            f'원래 문장: {log.get("text", "")}\n'
            f'고친 문장: {log.get("fixed", "")}\n'
            "(둘이 같으면 원래 문장이 맞았다는 뜻)\n"
        )

    try:
        from backend.student import notebook_text
        notebook_block = notebook_text(body.student)
    except Exception:
        notebook_block = "(모름)"

    prompt = PROMPT.format(
        screen=ctx.screen or "(모름)", unit=ctx.unit or "(모름)", rule_id=ctx.rule_id or "(없음)",
        log_block=log_block, history_block=_history_block(body.student), notebook_block=notebook_block,
        faq_block=_faq_block(all_faqs), question=question,
    )
    try:
        out = llm.generate_json(prompt)
    except llm.LLMError as e:
        return {"answer": "", "source": [], "offtopic": True, "error": str(e)}
    llm_info = out.pop("_llm", {})

    if bool(out.get("wants_more")):
        # 정규식(_similar_match)이 못 잡은 "비슷한/다른 거" 표현을 LLM이 의도로 잡아준 경우 —
        # 실제 답은 LLM이 아니라 결정적 로직(_alternative_response)에 맡긴다(2026-09-10)
        alt = _alternative_response(body.student, all_faqs)
        if alt is not None:
            alt["llm"] = llm_info
            return alt

    faq = next((f for f in all_faqs if f["id"] == out.get("faq_id")), None)
    source = [{"chunk_id": rid} for rid in (faq.get("rule_ids") or [])] if faq else []
    if faq:
        source.append({"chunk_id": faq["id"]})
    if log and log.get("rule_id") and not any(s["chunk_id"] == log["rule_id"] for s in source):
        source.append({"chunk_id": log["rule_id"]})

    answer = out.get("answer") or ""
    offtopic = bool(out.get("offtopic"))
    if offtopic and answer.strip() and "선생님" not in answer:
        # 모델이 offtopic=true 라면서도 answer 는 유용하게 주는 경우가 잦음 — 프롬프트가 정한
        # 진짜 못 답한 응답("선생님한테 물어볼까?")만 그 문구를 쓰므로 길이 대신 이걸로 판단
        print(f"[ask] offtopic=true인데 '선생님' 문구가 없어서 offtopic 취소: {answer!r}", flush=True)
        offtopic = False

    return {
        "answer": answer,
        "source": source,
        "offtopic": offtopic,
        "suggested": [q for q in (out.get("suggested") or []) if isinstance(q, str)][:2],
        "llm": llm_info,
    }
