"""
물어보기 챗 (PRD 4.4, 화면/통합은 팀장 소관 · 백엔드가 아직 없어서 TTS 담당이 임시로 준비)

POST /api/ask
body: {"student", "question", "context": {"screen","unit","rule_id","log_id"}}
→ {"answer", "source": [{"chunk_id"}], "offtopic", "suggested": [...]}
(common.js 의 askChat() 이 이미 이 형식을 기다림 — 필드 바꾸면 그쪽도 같이 바꿔야 함)

1) 로컬 매칭(faq.jsonl→rules.jsonl 단어 겹침) 먼저 — 되면 Gemini 호출 없이 즉시 반환
2) 안 되면 Gemini 폴백(faq 전체를 프롬프트에 넣고 고르게 함 — rag.search 완성되면
   1위 조각만 넣는 방식으로 바꿀 수 있음)

context.log_id 가 있으면 sentence_log.jsonl 에서 그 순간의 원문·고친 문장을 찾아 프롬프트에
넣는다("아까 말한 거 고쳐줘"에 다시 추론 안 하고 /fix 결과를 그대로 씀). student.py 의
notebook_text() 도 개인화 참고 자료로 넣는다(답 근거는 여전히 FAQ).
"""
import json
import re
from pathlib import Path

from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend import golden
from backend.config import settings

router = APIRouter(tags=["ask"])
_client: genai.Client | None = None
SENTENCE_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "sentence_log.jsonl"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


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


def _best_match(question: str, items: list[dict], candidates_of) -> tuple[dict | None, float]:
    """단어 겹침 기반 매칭. frontend/js/common.js 의 faqMatch()와 같은 알고리즘 —
    서버가 먼저 이걸로 찾아보고, 못 찾을 때만 Gemini 로 넘어간다(할당량 절약, 응답도 빠름)."""
    qs = _norm_words(question)
    best, best_score = None, 0.0
    for item in items:
        for cand in candidates_of(item):
            cs = _norm_words(cand)
            if not cs:
                continue
            # 부분 문자열 겹침은 두 단어 다 2글자 이상일 때만 인정 — "뭐"/"뭐예요"처럼
            # 한 글자만 겹쳐서 상관없는 문장이 오탐되는 걸 막는다. 완전히 같은 단어는 길이 상관없이 인정.
            hit = sum(1 for w in cs if any(w == x or (len(w) >= 2 and len(x) >= 2 and (w in x or x in w)) for x in qs))
            score = hit / len(cs)
            if score > best_score:
                best_score, best = score, item
    return best, best_score


def _local_match(question: str, faq_list: list[dict], rule_list: list[dict]) -> dict | None:
    """1순위 faq.jsonl(질문+variants), 2순위 rules.jsonl(유형명+짧은 힌트) 순으로 로컬 매칭.
    둘 다 0.5 미만이면 None → 호출부가 Gemini 로 넘어간다."""
    faq, faq_score = _best_match(question, faq_list, lambda f: [f["question"]] + (f.get("variants") or []))
    if faq_score >= 0.5:
        source = [{"chunk_id": rid} for rid in (faq.get("rule_ids") or [])] + [{"chunk_id": faq["id"]}]
        return {"answer": faq["answer"], "source": source, "offtopic": False, "suggested": []}

    rule, rule_score = _best_match(question, rule_list, lambda r: [r["type"], r.get("short", "")])
    if rule_score >= 0.5:
        return {"answer": rule.get("short") or rule["text"], "source": [{"chunk_id": rule["id"]}],
                "offtopic": False, "suggested": []}

    return None


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
6. 출력은 아래 JSON 하나만. 다른 말은 쓰지 않는다.

## 지금 상황
화면: {screen} · 유닛: {unit} · 방금 나온 규칙: {rule_id}
{log_block}
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
  "suggested": ["이어서 물어볼 만한 짧은 질문 2개"]
}}"""


_CORRECTNESS_PATTERN = re.compile(r"맞는\s*문장|맞아요|맞나요|맞을까요|맞습니까|틀렸어요|틀린\s*문장|틀려요")

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
    out = _ask_gemini(prompt)
    ok = bool(out.get("ok", True))
    rule = golden.find_rule(out.get("rule_id")) if not ok else None
    sentence = (out.get("sentence") or "").strip()
    if ok:
        answer = f'네, "{sentence}"는 맞는 문장이에요! 👍' if sentence else "네, 맞는 문장이에요!"
    else:
        answer = f'{(out.get("why") or "").strip()} "{out.get("fixed", "")}"가 맞아요.'.strip()
    return {"answer": answer, "source": [{"chunk_id": rule["id"]}] if rule else [], "offtopic": False, "suggested": []}


def _ask_gemini(prompt: str) -> dict:
    """JSON 만 받는다. 모델이 코드펜스를 붙여도 벗겨서 파싱 (tutor.py 의 _ask_gemini 와 같은 패턴)."""
    resp = _get_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


@router.post("/ask")
def ask(body: AskIn):
    question = body.question.strip()
    if not question:
        return {"answer": "", "source": [], "offtopic": True}

    if _CORRECTNESS_PATTERN.search(question):
        if not settings.has_api_key:
            return {"answer": "", "source": [], "offtopic": True, "error": "GEMINI_API_KEY 미설정"}
        try:
            return _check_correctness(question)
        except Exception:
            return _CORRECTNESS_FALLBACK

    all_faqs = golden.faqs()
    all_rules = golden.rules()
    if not all_faqs and not all_rules:
        return {"answer": "", "source": [], "offtopic": True, "error": "faq.jsonl/rules.jsonl 이 없음"}

    # 1) 로컬 매칭 먼저 — faq/rules 안에서 바로 찾아지면 Gemini 호출 없이 즉시 반환
    local = _local_match(question, all_faqs, all_rules)
    if local is not None:
        return local

    # 2) 로컬 매칭 실패 → Gemini 폴백 (faq 전체를 프롬프트에 넣고 고르게 함)
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
        log_block=log_block, notebook_block=notebook_block, faq_block=_faq_block(all_faqs), question=question,
    )
    try:
        out = _ask_gemini(prompt)
    except Exception as e:
        return {"answer": "", "source": [], "offtopic": True, "error": str(e)}

    faq = next((f for f in all_faqs if f["id"] == out.get("faq_id")), None)
    source = [{"chunk_id": rid} for rid in (faq.get("rule_ids") or [])] if faq else []
    if faq:
        source.append({"chunk_id": faq["id"]})
    if log and log.get("rule_id") and not any(s["chunk_id"] == log["rule_id"] for s in source):
        source.append({"chunk_id": log["rule_id"]})

    return {
        "answer": out.get("answer") or "",
        "source": source,
        "offtopic": bool(out.get("offtopic")),
        "suggested": [q for q in (out.get("suggested") or []) if isinstance(q, str)][:2],
    }
