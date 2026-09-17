"""
물어보기 챗 (PRD 4.4, 화면/통합은 팀장 소관 · 백엔드가 아직 없어서 TTS 담당이 임시로 준비)

POST /api/ask
body: {"student", "question", "context": {"screen","unit","rule_id","log_id","text","source","level"}}
→ {"answer", "source": [{"chunk_id"}], "offtopic", "suggested": [...]}
(common.js 의 askChat() 이 이미 이 형식을 기다림 — 필드 바꾸면 그쪽도 같이 바꿔야 함)

ask() → _llm_first_answer()(모델 우선 경로, 팀장 요청 2026-09-17로 기본 전환, 2026-09-17 결정적
매칭 폴백(_hybrid_answer 등)은 완전히 제거 — 코드가 답을 정하지 않고, 지금 유닛 자료 + 검색 자료 +
오답노트 + 최근 대화를 모델에 주고 모델이 답·출처·교과서 밖 여부를 정한다. 자료에 없어도 초등 영어
질문이면 답하고 "교과서 밖" 표시. 코드가 직접 정하는 건 두 가지뿐: 인사·감정 고정 답
(_intent_fixed_reply), 영어 문장 판정(_check_correctness). 모델이 주장한 출처(used_ids)는
그대로 믿지 않고 _textbook_coverage()가 답변 내용과 교과서 데이터를 코드로 대조해서 검증한다.

context.log_id 가 있으면 sentence_log.jsonl 에서 그 순간의 원문·고친 문장을 찾아 프롬프트에
넣는다("아까 말한 거 고쳐줘"에 다시 추론 안 하고 /fix 결과를 그대로 씀). student.py 의
notebook_text() 도 개인화 참고 자료로 넣는다.

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

router = APIRouter(tags=["ask"])
SENTENCE_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "sentence_log.jsonl"
CHAT_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "chat_log.jsonl"
CHAT_HISTORY_WINDOW_SEC = 180   # 이 안이면 "같은 대화"로 보고 그거/이거 지시어 힌트로 씀
CHAT_HISTORY_MAX_TURNS = 2
DEFAULT_LEVEL = 3   # ctx.level 이 없을 때(화면이 안 보냈거나 None) 쓰는 기본 학년 — 5곳에 흩어져
                    # 있던 "or 3" 리터럴을 하나로 모음(2026-09-16)


class AskContext(BaseModel):
    screen: str | None = None
    unit: str | None = None
    rule_id: str | None = None
    log_id: str | None = None
    text: str | None = None     # 고쳐줘 누르기 전 입력·들린 문장 (log_id 아직 없을 때, 2026-09-14 tutor.js)
    source: str | None = None   # text 가 어디서 왔는지(타이핑/음성) — 지금은 참고용, 답에는 안 씀
    level: int | None = None    # 학생 학년 (2026-09-14 common.js) — search_textbook(level=)에 씀, 없으면 3


class AskIn(BaseModel):
    student: str = "A"
    question: str
    context: AskContext = AskContext()


def _norm_words(text: str) -> list[str]:
    # "make+목적어+형용사가"처럼 "+"/"/"로 붙은 단어가 공백 split()으론 하나로 뭉쳐서 내용어 판별이
    # 부정확해지는 문제가 있었음(2026-09-11) — "+"/"/"도 구분자로 취급해 쪼갠다.
    cleaned = re.sub(r"[?？.!,]", "", text.lower())
    return [w for w in re.split(r"[\s+/]+", cleaned) if w]


_GENERIC_WORDS = {
    "뭐예요", "뭐야", "무슨", "뜻이", "뜻이에요", "뜻인가요", "뜻이야",
    # "X랑 Y 뭐가 달라요?"류 비교 질문의 꼬리 표현 — 토픽(X, Y)이 아니라 어느 비교 질문에나
    # 붙는 상투어라, 이것만으로 겹쳐서 무관한 FAQ가 이기는 문제가 있었음(2026-09-11,
    # "many랑 much 차이" 질문이 "want랑 뭐가 달라요"(F-81, want vs would like)에 잘못 매칭됨).
    "뭐가", "달라요", "다른가요", "다르나요", "차이가", "차이는", "차이예요",
    # "~할 때 어떻게 말해요?"/"~ 뭐 써요?"류 — 문법 설명 FAQ 대부분이 이런 상투적 질문
    # 형식(어떻게/뭐/때/할+동사)을 쓰다 보니, 진짜 주제 단어 없이 이 틀만 겹쳐도 무관한 FAQ가
    # 이겨버리는 문제가 광범위하게 있었음(2026-09-14, 76개 질문 테스트에서 8건 재현 — "봄 전치사"가
    # "This/These"에, "버스 타는 법"이 "문 닫으라는 명령문"에 매칭되는 등). 의문사·연결어·상투적
    # 동사를 전부 제외.
    "어떻게", "때", "할", "써요", "와요", "해요", "돼요", "말해요", "붙여요",
    "쓰나요", "오나요", "써야", "와야", "되나요", "하나요", "뭐",
    # "내가 뭘 자주 틀렸지?"류 — 주어/목적어 자리의 1인칭 대명사·의문대명사는 어느 질문에나
    # 붙어서 내용어 개수만 부풀리고 주제 판별엔 안 쓰임(2026-09-14, 오답노트 비어있음 가드가
    # "내가 뭘 자주 틀렸지?"는 내용어 4개로 세서 안 걸리고, LLM이 프롬프트 예시 문장을 학생의
    # 진짜 기록인 것처럼 지어내 답한 사례로 재현).
    "내가", "나는", "제가", "저는", "뭘",
}

# "answer 내용이 rule 내용과 실제로 겹치는지" 확인할 때 이 단어들만 겹친 건 무시 — 의미 있는
# 주제어가 아니라 어느 설명문에나 나오는 연결어라(2026-09-14, "He like pizza 이거 맞아?"가
# 3인칭단수를 맞게 설명해놓고 "때" 한 단어만 겹쳐서 무관한 R-29(How much/many)가 근거로 붙음).
_WEAK_OVERLAP_WORDS = {"때", "수", "것", "안", "예", "예:", "그", "이", "저"}

# "뭐가/뭐예요"류 필러 표현의 흔한 오타(모/머)·붙여쓰기(뭐가달라요)가 _GENERIC_WORDS에 정확히
# 안 걸려서, 그 단어만으로 다단어 질문(2개 이상 후보 전체와 안 겹치면 폐기, D2 규칙)이 통째로
# 폐기되던 문제(2026-09-16, 100문항 수동 테스트 — "go랑 went 머가 달라요"/"뭐가달라요"가
# offtopic으로 잘못 거절됨). 앞이 공백/문장 시작일 때만 치환 — "이모가 영어로 뭐예요?"(이모=aunt)
# 처럼 진짜 단어 중간의 모/가를 건드리지 않기 위해 단어 시작 위치만 잡는다. 뒤쪽은 "뭐가달라요"처럼
# 다른 말이 붙어 한 토큰으로 뭉쳐도 잡히게 경계를 안 둔다.
_FILLER_TYPO_FIXES = [
    (re.compile(r"(?:^|(?<=\s))[모머](가|예요|에요|에오|야)"), r"뭐\1"),
    # "머임"만 처리 — "모임"(gathering, 진짜 단어)까지 같이 걸리지 않게 모/머를 묶지 않고 머만 지정.
    (re.compile(r"(?:^|(?<=\s))머임"), "뭐예요"),
    (re.compile(r"(?<!이)에요"), "예요"),
    (re.compile(r"이에오"), "이에요"),
    (re.compile(r"맏(아요|나요)"), r"맞\1"),
]


_STANDALONE_DEMONSTRATIVE = re.compile(r"(?:^|(?<=\s))(이거|그거|이것|그것)(?=\s|$|[?!.,])")


def _normalize_filler_typos(question: str) -> str:
    for pat, repl in _FILLER_TYPO_FIXES:
        question = pat.sub(repl, question)
    if re.search(r"[A-Za-z]", question):
        # "water 이거 머임?"처럼 질문에 영단어가 이미 있으면 "이거/그거"는 직전 대화가 아니라
        # 그 단어를 가리키는 말인데, 그대로 두면 임베딩 유사도가 눈에 띄게 떨어져서(실측 —
        # "water 뭐예요?" 0.878 → "water 이거 뭐예요?" 0.844, F-05 기준) 문턱을 못 넘고
        # 거절돼버린다(2026-09-16, 오프토픽/필러 경계 테스트에서 발견). 영단어가 없는 순수
        # 이어가기 질문("이거 왜 틀렸어?")은 이 가드에 안 걸려 그대로 남는다.
        question = re.sub(r"\s+", " ", _STANDALONE_DEMONSTRATIVE.sub(" ", question)).strip()
    return question


def _content_words(text: str) -> list[str]:
    """"무슨 뜻이에요"류 범용 의문 표현만 뺀 단어 목록 — 이것만 겹쳐서 서로 다른 단어를
    묻는 질문끼리 오매칭되는 걸 막는다(2026-09-10, "elephant 뜻이 뭐예요?"가 F-06(zoo)에
    잘못 매칭된 사례)."""
    return [w for w in _norm_words(text) if w not in _GENERIC_WORDS]


_PAREN = re.compile(r"\([^)]*\)")


                                                                     # 0이 아니라 최소 가중치는 남긴다


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


_CORRECTNESS_PATTERN = re.compile(
    r"맞는\s*문장|틀린\s*문장|맞습니까|"
    r"맞아|맞나|맞지|맞을까|틀렸어|틀렸나|틀렸지|틀려"
)   # "맞아요"뿐 아니라 "맞아?"처럼 요 없는 구어체도 잡음(2026-09-10)

_CORRECTNESS_FALLBACK = {
    "answer": "오, 그건 내가 여기서 바로 맞다 틀리다 봐주기는 어려워! "
              "'내 문장 말하기'에서 그 문장을 말하고 [고쳐줘]를 눌러보면 정확하게 확인해줄게 🙂",
    "source": [], "offtopic": False, "suggested": [],
}

CORRECTNESS_PROMPT = """너는 초등학교 {grade}에게 영어를 가르치는 선생님이다. 학생이 문장이 맞는지 물어봤다.
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


def _correctness_candidate_rules(sentence: str, k: int = 8) -> list[dict] | None:
    """/fix가 이미 쓰는 검색(search_examples+search_rules를 merge_candidates로 합침, 실측
    hit@1 77%·hit@3 91%)을 재사용해 판정 대상 문장과 관련된 규칙 후보만 추린다(2026-09-16) —
    CORRECTNESS_PROMPT가 규칙 100개를 통째로 넣어 ctx8k(8192토큰) 중 7,335토큰을 써버리던 위험을
    없애고, LLM이 100개 중 헤매지 않게 한다. k=8은 /fix의 RAG_TOP_K와 동일(5→8로 늘렸을 때
    82→84% 개선된 실측값 재사용). 검색 실패(색인 없음 등)하면 None — 호출부가 golden.rules()
    전체로 폴백한다.

    unit="ALL"(유닛 무관 공통 규칙, 100개 중 10개 — 과거시제 R-31 등)은 검색 순위와 무관하게
    항상 포함한다 — /fix(tutor.py)도 이렇게 한다(extra_ids). 임베딩 검색이 이 학생 문장과
    표면적으로 안 겹치면 순위에서 밀릴 수 있는데, 공통 규칙은 어느 문장에나 적용될 수 있어
    놓치면 안 된다(2026-09-16 발견 — /fix식 검색을 흉내내면서 이 부분만 빠뜨렸었음). 유닛별
    강제 포함(지금 화면의 유닛 규칙)까지는 안 함 — _check_correctness()가 애초에 unit을 안
    받아서 범위가 더 크다, 우선 ALL만."""
    try:
        from backend import embedding, indexing, textbook
        from backend.rag import search_rules
    except ImportError:
        return None
    try:
        qvec = embedding.embed_query(sentence)
        ex_cands = textbook.search_examples(sentence, k=k, qvec=qvec)
        rule_cands = search_rules(sentence, k=k)
    except indexing.IndexUnavailableError:
        return None
    except Exception:
        return None
    merged = textbook.merge_candidates(ex_cands, rule_cands, k=k)
    if not merged:
        return None
    seen = {c["id"] for c in merged}
    merged += [r for r in golden.rules() if r.get("unit") == "ALL" and r["id"] not in seen]
    return merged


def _check_correctness(question: str, level: int = 3) -> dict:
    """"맞는 문장이에요?" 류 질문을 /fix 를 부르지 않고 자체 판정한다(sentence_log/notebook 에
    기록 안 남김 — 궁금해서 물어본 거지 "내 문장 말하기" 연습이 아니라서). 실패하면 안내 문구로
    폴백(호출부에서 처리).

    level: 프롬프트의 페르소나 문구("초등학교 N학년")에만 씀 — 이전엔 "3~4학년"으로
    고정돼 있어서 6학년 학생한테도 그렇게 답했다(2026-09-16 발견)."""
    # question엔 판정 대상 문장 외에 한국어 메타 질문("이거 맞아?")도 섞여 있어서, 검색 정확도를
    # 위해 영어 토큰만 추려 붙인 걸 검색 질의로 쓴다(2026-09-16).
    eng_sentence = " ".join(re.findall(r"[A-Za-z][A-Za-z']*", question)) or question
    rules = _correctness_candidate_rules(eng_sentence) or golden.rules()
    prompt = CORRECTNESS_PROMPT.format(grade=f"{level}학년",
                                        rules_block="\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in rules), question=question)
    out = llm.generate_json(prompt)
    llm_info = out.pop("_llm", {})
    ok = bool(out.get("ok", True))
    # golden.find_rule()은 rules.jsonl을 처음부터 다시 읽는데(캐싱 없음), LLM이 고른 rule_id는
    # 방금 프롬프트에 보여준 rules 후보 중 하나일 가능성이 높다 — 거기서 먼저 찾고, 없을 때만
    # (LLM이 후보 밖 id를 골랐을 때만) find_rule()로 폴백해 중복 읽기를 없앤다(2026-09-16).
    rule = None
    if not ok:
        rid = out.get("rule_id")
        rule = next((r for r in rules if r["id"] == rid), None) or (golden.find_rule(rid) if rid else None)
    sentence = (out.get("sentence") or "").strip()
    if ok:
        answer = f'네, "{sentence}"는 맞는 문장이에요! 👍' if sentence else "네, 맞는 문장이에요!"
    else:
        answer = f'{(out.get("why") or "").strip()} "{out.get("fixed", "")}"가 맞아요.'.strip()
    # LLM이 "why" 설명은 맞게 쓰고 rule_id 필드만 무관한 걸 골라서 answer 근거로 엉뚱한 규칙이
    # 딸려 나오는 경우가 있었음(2026-09-14, "He like pizza 이거 맞아?"가 3인칭단수를 제대로
    # 설명해놓고 rule_id는 R-29(How much/many 의문문)로 잘못 채워서 suggested가 엉뚱하게 나옴) —
    # answer 내용이 그 규칙의 실제 내용과 겹치는지 확인하고, 안 겹치면 근거로 안 붙인다(source
    # 경로의 Fix C와 같은 방식).
    overlap = (set(_content_words(answer)) & set(_content_words(rule["type"] + " " + rule["text"]))) - _WEAK_OVERLAP_WORDS if rule else set()
    if rule and not overlap:
        rule = None   # "때/수/것"처럼 의미 없는 연결어 하나만 겹쳐도 통과되던 문제 방지
    suggested = _followup_questions([rule["id"]], golden.faqs()) if rule else []
    return {"answer": answer, "source": [{"chunk_id": rule["id"]}] if rule else [], "offtopic": False,
            "suggested": suggested, "llm": llm_info}


@router.post("/ask")
def ask(body: AskIn):
    result = _llm_first_answer(body)
    _log_chat_turn(body.student, body.question.strip(), result.get("answer", ""), result.get("source"))
    return result


# ── 의도 가르기 (계약 문서 2-1절 0번, 2026-09-14 저녁) — 검색 전에 코드로 먼저 가른다 ──────────
_INTENT_FILLER = r"(?:나는?|저는?|오늘|요즘|진짜|너무|정말)\s*"
_INTENT_REPLIES = [
    # "안녕"만 잡고 "안녕하세요"(오히려 더 흔한 존댓말 인사)는 안 잡혀서 검색으로 새고 있었다
    # (2026-09-16 실사용 테스트 재현 — "Good morning!"이라는 뜬금없는 답이 나감).
    (re.compile(r"^(안녕(하세요|하십니까|하신가요)?|hi|hello|하이)[!~.\s]*$", re.IGNORECASE), "안녕! 오늘 배우는 것에 대해 뭐든 물어봐 😊"),
    (re.compile(rf"^({_INTENT_FILLER})*(고마워|고맙습니다|감사해요|감사합니다)[요]?[!~.\s]*$"), "천만에! 더 궁금한 거 있으면 또 물어봐."),
    (re.compile(rf"^({_INTENT_FILLER})*(피곤해|졸려|힘들어|배고파)[요]?[ㅠㅜ!~.\s]*$"), "조금 쉬었다 해도 괜찮아! 준비되면 다시 물어봐줘."),
    (re.compile(rf"^({_INTENT_FILLER})*(심심해|재미없어)[요]?[!~.\s]*$"), "그럼 문제 하나 풀어볼까? 궁금한 거 있으면 물어봐도 좋고!"),
    # "너 사람이야 AI야?" 류 정체성 질문 — 검색 재료(패턴/단어)와 안 겹쳐서 LLM이 근거 없이
    # 지어내다가, 안전장치가 답을 버리고 엉뚱한 1위 단어("hi")로 대체하던 문제(2026-09-16 재현).
    (re.compile(r"^(너는?|넌).{0,10}(사람|인간|ai|로봇|컴퓨터).{0,15}(이야|이에요|야|예요)\s*\??$", re.IGNORECASE),
     "나는 너의 영어 공부를 도와주는 AI 선생님이야! 궁금한 거 있으면 편하게 물어봐 😊"),
]


def _intent_fixed_reply(question: str) -> dict | None:
    """인사·감사·감정 표현은 검색 없이 고정 문구로 — 앞에 "나는/오늘/너무" 같은 흔한 꾸밈말만
    허용하고 그 뒤로는 끝까지 일치해야 걸림("안녕이 영어로 뭐야?"는 지식 질문이라 안 걸리고,
    "나 오늘 피곤해"는 걸림 — 2026-09-16, 문장 전체 일치만으론 후자를 놓쳐서 lookup_word가
    "오늘"을 단어 뜻 질문으로 착각하는 문제 재현됨)."""
    q = question.strip()
    for pattern, reply in _INTENT_REPLIES:
        if pattern.match(q):
            return {"answer": reply, "source": [], "offtopic": False, "suggested": []}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 모델 우선 경로 (팀장 요청, 2026-09-17 기본 채택 — 옛 결정적 매칭 폴백은 제거됨)
#   원칙: 코드가 답을 정하지 않는다. 지금 유닛 자료 + 검색 자료 + 오답노트 + 최근 대화를 모델에 주고
#   모델이 답·출처·교과서 밖 여부를 정한다. 자료에 없어도 초등 영어 질문이면 답하고 "교과서 밖" 표시.
#   남긴 코드 판정: 인사·감정 고정 답(_intent_fixed_reply), 영어 문장 판정(_check_correctness).
#   모델이 주장한 출처는 그대로 안 믿고 _textbook_coverage()가 답변 내용을 교과서 데이터와 코드로
#   대조해서 검증한다(2026-09-17).
# ══════════════════════════════════════════════════════════════════════════════
LLM_FIRST_PROMPT = """너는 초등학교 {grade}에게 영어를 가르치는 다정한 선생님 챗봇이다. 학생은 지금 {where} 화면에 있다.

## 답하는 원칙
1. 아래 "교과서 자료"에 답이 있으면 그걸로 답하고 used_ids 에 실제로 쓴 자료의 id 를 적는다 (from_textbook=true).
2. 자료에 없어도 초등 영어 공부 질문(단어 뜻, 숫자·요일·색깔·인사 같은 기본 표현, 짧은 문장의 뜻, "OO 를 영어로", 문법, 문장이 맞는지)이면 네가 아는 대로 정확하게 답한다 (from_textbook=false, used_ids 는 빈 목록).
3. 영어 공부와 상관없는 질문(오늘 메뉴, 날씨, 게임 등)은 offtopic=true 로 하고 answer 에 "그건 영어 공부 질문이 아니라서 답하기 어려워. 영어로 뭐라고 하는지 궁금한 게 있으면 물어봐!" 처럼 한 문장만 쓴다.
4. 인사·기분 표현에는 짧고 다정하게 한 문장 (offtopic=false).
5. 문장이 맞는지 물으면 맞는지 말하고, 틀렸으면 고친 문장을 보여 준다. 근거는 자료의 문법 규칙이 있으면 그것.
6. 자주 틀리는 것·뭘 틀렸는지 물으면 "이 학생의 오답노트"로 답한다. 비어 있으면 아직 기록이 없다고 한다.
7. "지금 무슨 유닛이야" 같은 화면 상황 질문은 위 화면 정보로 답한다.
8. answer 는 한국어 2~3문장, 초등학생이 읽기 쉽게. 영어는 영어 그대로. 목록을 물으면(숫자 1~5 등) 짧은 목록으로 써도 된다. 없는 내용을 지어내지 않는다.

## 교과서 자료 (지금 유닛 것 + 검색으로 찾은 것. [id] (종류·유닛) 내용)
{materials}
{log_block}
## 이 학생의 오답노트
{notebook_block}
{history_block}
## 학생 질문
{question}

## 출력 JSON 하나만
{{"answer": "...", "used_ids": ["p-0121"], "from_textbook": true 또는 false, "own_knowledge": true 또는 false, "offtopic": true 또는 false}}
own_knowledge 는 자료에 없어서 네가 아는 영어 지식으로 답했을 때만 true. 화면 정보·오답노트·대화 내용으로 답했으면 false."""

_OUT_OF_TEXTBOOK_PREFIX = "📖 교과서엔 없지만 알려줄게요. "


def _llm_first_materials(question: str, ctx: AskContext, student: str, level: int) -> tuple[str, dict[str, str], dict[str, list[str]]]:
    """모델에 줄 자료 블록과 (id → 유닛), (FAQ id → rule_ids) 를 만든다. 검색 실패해도 지금 유닛 자료는 준다."""
    from backend import embedding, textbook
    lines: list[str] = []
    seen: set[str] = set()
    unit_of: dict[str, str] = {}
    faq_rules: dict[str, list[str]] = {}

    def add(mid: str, unit: str | None, text: str) -> None:
        if not mid or mid in seen:
            return
        seen.add(mid)
        if unit:
            unit_of[mid] = unit
        lines.append(f"- [{mid}] {text}")

    # 지금 유닛 단어·문장 (결정적, 검색 없이)
    if ctx.unit:
        for w in golden.words(level, ctx.unit)[:12]:
            add(w["id"], ctx.unit, f'(단어·{ctx.unit}) {w["word"]} — {w["meaning"]}' + (f' (예: {w["example"]})' if w.get("example") else ""))
        for pt in golden.patterns(level, ctx.unit)[:8]:
            add(pt["id"], ctx.unit, f'(교과서 문장·{ctx.unit}) {pt["text"]} — {pt.get("meaning", "")}')
    # 방금 규칙(화면이 넘긴 rule_id 또는 직전 대화의 규칙)
    rule_id = ctx.rule_id
    if not rule_id:
        last = next((t for t in reversed(_recent_chat_turns(student, max_turns=5)) if t.get("rule_ids")), None)
        if last:
            rule_id = last["rule_ids"][0]
    if rule_id:
        r = golden.find_rule(rule_id)
        if r:
            add(r["id"], r.get("unit"), f'(방금 다룬 문법 규칙·{r.get("unit", "")}) {r["type"]}: {r["text"]}' + (" 예: " + " / ".join((r.get("examples") or [])[:2]) if r.get("examples") else ""))
    # 질문의 영어 낱말이 본문·예문에 든 문법 규칙 (임베딩 없이 100개 훑기): "go 랑 went" → R-31
    for r in _rules_by_english_words(question, golden.rules()):
        add(r["id"], r.get("unit"), f'(문법 규칙·{r.get("unit", "")}) {r["type"]}: {r["text"]}' + (" 예: " + " / ".join((r.get("examples") or [])[:2]) if r.get("examples") else ""))
    # 단어장 정확 조회 (임베딩 없이, 전 학년): "안녕하세요 영어로" → hello (Unit01). 검색 점수가 문턱을 못 넘어도 여기서 잡힌다
    try:
        for w in textbook.lookup_word(question, level=6)[:5]:
            add(w["id"], w.get("unit"), f'(단어·{w.get("unit", "")}) {w["word"]} — {w["meaning"]}' + (f' (예: {w["example"]})' if w.get("example") else ""))
    except Exception as e:  # noqa: BLE001
        print(f"[ask][llm-first] 단어장 조회 실패: {e}", flush=True)
    # 검색 (FAQ · 규칙 별칭 · 교과서 문장·단어)
    try:
        qvec = embedding.embed_query(question)
    except Exception as e:  # noqa: BLE001
        print(f"[ask][llm-first] 임베딩 실패 → 지금 유닛 자료만: {e}", flush=True)
        qvec = None
    if qvec is not None:
        try:
            for f in textbook.search_faq(question, k=3, rule_id=rule_id, qvec=qvec):
                if f.get("score", 0) >= 0.70:
                    faq_rules[f["id"]] = list(f.get("rule_ids") or [])
                    add(f["id"], f.get("unit"), f'(자주 묻는 질문) Q: {f["question"]} → A: {f["answer"]}')
            for h in textbook.search_rule_aliases(question, k=3, qvec=qvec):
                r = golden.find_rule(h["id"]) if h.get("score", 0) >= 0.70 else None
                if r:
                    add(r["id"], r.get("unit"), f'(문법 규칙·{r.get("unit", "")}) {r["type"]}: {r["text"]}' + (" 예: " + " / ".join((r.get("examples") or [])[:2]) if r.get("examples") else ""))
            tb = textbook.search_textbook(question, level=level, k_pattern=4, k_word=4, qvec=qvec)
            for pt in tb.get("patterns") or []:
                if pt.get("score", 0) >= 0.70:
                    add(pt["id"], pt.get("unit"), f'(교과서 문장·{pt.get("unit", "")}) {pt["text"]} — {pt.get("meaning", "")}')
            for w in tb.get("words") or []:
                if w.get("score", 0) >= 0.70:
                    add(w["id"], w.get("unit"), f'(단어·{w.get("unit", "")}) {w["word"]} — {w["meaning"]}' + (f' (예: {w["example"]})' if w.get("example") else ""))
        except Exception as e:  # noqa: BLE001
            print(f"[ask][llm-first] 검색 실패 → 지금 유닛 자료만: {e}", flush=True)
    return ("\n".join(lines) if lines else "(없음)"), unit_of, faq_rules


def _rule_search_text(r: dict) -> str:
    return " ".join([r.get("text") or "", *(r.get("examples") or []), r.get("wrong_example") or ""]).lower()


def _rules_by_english_words(question: str, rules: list[dict], k: int = 3) -> list[dict]:
    """질문에 든 영어 낱말(go, went, an…)이 본문·예문에 단어 단위로 들어 있는 규칙을 겹친 수 순으로 k개.
    규칙 100개를 그냥 훑는다(1ms 안팎) — "go 랑 went 랑 뭐가 달라" 처럼 한·영이 섞인 짧은 질문은 임베딩이
    엉뚱한 걸 높은 점수로 올리고 R-31(과거시제)을 놓쳐서(9/17 실측) 낱말 검색이 더 정확하다."""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", question) if len(w) >= 2 and w.lower() not in _EN_STOP}
    if not words:
        return []
    scored = []
    for r in rules:
        text = _rule_search_text(r)
        body = (r.get("text") or "").lower()
        # 영어 낱말 경계는 영문자 기준 — 파이썬 \b 는 한글도 글자로 봐서 "go는" 의 go 를 못 잡는다
        hit = sum(1 for w in words if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text))
        if hit:
            in_body = sum(1 for w in words if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", body))   # 본문(설명)에 든 낱말을 예문에만 든 것보다 우선
            scored.append((hit, in_body, r))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [r for _, _, r in scored[:k]]


_TB_INDEX: dict | None = None
_EN_STOP = {"i", "a", "an", "the", "to", "is", "am", "are", "was", "were", "you", "it", "in", "on", "at", "and", "or", "my", "your",
            "this", "that", "of", "for", "with", "he", "she", "we", "they", "do", "does", "have", "has", "not", "yes", "no", "ok", "unit"}


def _norm_en(text: str) -> str:
    return " ".join(re.sub(r"[^a-z' ]+", " ", (text or "").lower()).split())


def _textbook_index() -> dict:
    """전 학년·전 유닛 단어장/패턴 색인 (한 번만 만든다). word → (id, unit), 패턴 정규화 문장 → (id, unit), id → (종류, 본문, unit)."""
    global _TB_INDEX
    if _TB_INDEX is None:
        words, pats, by_id = {}, {}, {}
        for lv in golden.levels():
            for u in golden.units(lv["level"]):
                for w in golden.words(lv["level"], u["unit"]):
                    words.setdefault(w["word"].lower(), (w["id"], u["unit"]))
                    by_id[w["id"]] = ("word", w["word"].lower(), u["unit"])
                for pt in golden.patterns(lv["level"], u["unit"]):
                    pats.setdefault(_norm_en(pt["text"]), (pt["id"], u["unit"]))
                    by_id[pt["id"]] = ("pattern", _norm_en(pt["text"]), u["unit"])
        _TB_INDEX = {"words": words, "patterns": pats, "by_id": by_id}
    return _TB_INDEX


def _textbook_coverage(answer: str, used_ids: list[str]) -> tuple[list[str], list[str], float]:
    """답에 실제로 든 영어가 교과서에 있는지 코드로 대조한다.
    돌려주는 것: (답 내용과 맞는 자료 id 들, 그 자료들의 유닛, 답의 영어 내용어 중 교과서 단어 비율).
    모델이 적은 used_ids 는 그 자료의 본문이 답에 실제로 있을 때만 인정한다 (단어면 그 단어, 문장이면 그 문장; 규칙·FAQ 는 그대로)."""
    idx = _textbook_index()
    norm_ans = _norm_en(answer)
    tokens = [t for t in dict.fromkeys(re.findall(r"[a-z]+(?:'[a-z]+)?", answer.lower())) if len(t) >= 2 and t not in _EN_STOP]   # 따옴표('Hello!')는 낱말에 안 붙게
    ids: list[str] = []
    for u in used_ids:
        kind, body_text, _unit = idx["by_id"].get(u, (None, None, None))
        if kind is None:
            if u.startswith(("R-", "F-")):
                ids.append(u)
            continue
        if (kind == "word" and re.search(rf"\b{re.escape(body_text)}\b", norm_ans)) or (kind == "pattern" and body_text and body_text in norm_ans):
            ids.append(u)
    hit = 0
    for t in tokens:
        if t in idx["words"]:
            hit += 1
            wid = idx["words"][t][0]
            if wid not in ids and not any(idx["by_id"].get(i, ("",))[0] == "word" for i in ids):
                ids.append(wid)
    for ptxt, (pid, _unit) in idx["patterns"].items():
        if len(ptxt.split()) >= 2 and ptxt in norm_ans and pid not in ids:
            ids.append(pid)
    if tokens and not any(i.startswith("R-") for i in ids):
        best, best_hit = None, 0
        for r in golden.rules():
            text = _rule_search_text(r)
            h = sum(1 for t in tokens if re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", text))
            if h > best_hit:
                best, best_hit = r, h
        if best is not None and best_hit >= 2:
            ids.append(best["id"])
    units = [idx["by_id"][i][2] for i in ids if i in idx["by_id"]]
    for i in ids:
        if i.startswith("R-"):
            r = golden.find_rule(i)
            if r and r.get("unit"):
                units.append(r["unit"])
    ratio = hit / len(tokens) if tokens else 0.0
    return ids, units, ratio


def _llm_first_answer(body: AskIn) -> dict:
    question = _normalize_filler_typos(body.question.strip())
    if not question:
        return {"answer": "", "source": [], "offtopic": True}
    ctx = body.context
    level = ctx.level or DEFAULT_LEVEL

    # 코드가 정하는 건 두 가지만: 인사·감정 고정 답, 영어 문장 판정(전용 프롬프트가 더 정확 — 9/16 실측 93%)
    fixed = _intent_fixed_reply(question)
    if fixed is not None:
        return fixed
    asks_check = bool(_CORRECTNESS_PATTERN.search(question)) and not re.search(r"왜|어떻게", question)
    if asks_check and re.search(r"[A-Za-z]", question):
        try:
            return _check_correctness(question, level=level)
        except llm.LLMError:
            return _CORRECTNESS_FALLBACK
    if asks_check and (ctx.text or "").strip() and len(question) <= 15 and not re.search(r"[A-Za-z]", question):   # "이거 맞아?" 처럼 짧게 방금 문장을 가리킬 때만
        try:
            return _check_correctness(ctx.text.strip(), level=level)
        except llm.LLMError:
            return _CORRECTNESS_FALLBACK

    materials, unit_of, faq_rules = _llm_first_materials(question, ctx, body.student, level)
    unit_row = golden.find_unit(level, ctx.unit) if ctx.unit else None
    where = f'{ctx.unit} "{unit_row["title"]}"' if unit_row else (ctx.unit or "유닛 미정")
    screen_name = {"notebook": "오답노트", "shadow": "따라 말하기", "learn": "표현 익히기", "tutor": "문장 고쳐주기"}.get(ctx.screen or "", ctx.screen or "")
    if screen_name:
        where += f" · {screen_name}"

    log = _log_entry(ctx.log_id) if ctx.log_id else None
    if log:
        log_block = f'\n## 방금 학생이 만든 문장\n원래 문장: {log.get("text", "")}\n고친 문장: {log.get("fixed", "")}\n(둘이 같으면 원래 문장이 맞았다는 뜻)\n'
    elif ctx.text:
        log_block = f"\n## 학생이 방금 입력한 문장 (아직 안 고침)\n{ctx.text}\n"
    else:
        log_block = ""
    try:
        from backend.student import notebook_text
        notebook_block = notebook_text(body.student)
    except Exception:  # noqa: BLE001
        notebook_block = "(모름)"

    prompt = LLM_FIRST_PROMPT.format(grade=f"{level}학년", where=where, materials=materials, log_block=log_block,
                                     notebook_block=notebook_block, history_block=_history_block(body.student), question=question)
    try:
        out = llm.generate_json(prompt)
    except llm.LLMError as e:
        return {"answer": "지금 선생님 챗봇이 잠깐 쉬고 있어요. 조금 뒤에 다시 물어봐 줄래?", "source": [], "offtopic": True, "suggested": [], "error": str(e)}

    answer = str(out.get("answer") or "").strip()
    claimed = [u for u in (out.get("used_ids") or []) if isinstance(u, str) and (u in unit_of or u.startswith(("F-", "R-", "p-", "w-")))]
    offtopic = bool(out.get("offtopic"))
    if not answer:
        return {"answer": "음, 그 질문은 잘 모르겠어. 다른 말로 다시 물어봐 줄래?", "source": [], "offtopic": True, "suggested": []}
    # 교과서 여부는 모델 말이 아니라 코드가 대조해서 정한다 — 답에 든 영어 단어·문장이 교과서 단어장/패턴에 있으면 교과서 내용
    used, hit_units, ratio = _textbook_coverage(answer, claimed)
    # 질문의 영어 낱말이 전부 든 규칙("go 랑 went" → R-31)이 있으면 모델이 다른 규칙을 적었어도 그걸 첫 출처로 — 유닛 안내도 이 규칙 기준
    q_words = {w.lower() for w in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", question) if len(w) >= 2 and w.lower() not in _EN_STOP}
    q_rule = next(iter(_rules_by_english_words(question, golden.rules(), k=1)), None) if q_words else None
    if q_rule and all(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", _rule_search_text(q_rule)) for w in q_words):
        used = [q_rule["id"]] + [u for u in used if u != q_rule["id"]]
    has_english = bool(re.search(r"[A-Za-z]{2,}", answer))
    from_textbook = bool(used) and (ratio >= 0.5 or any(u.startswith(("R-", "F-", "p-")) for u in used))
    if not offtopic:
        # 유닛 안내는 규칙·FAQ·교과서 문장 기준. 단어만으로는 답의 영어가 거의 다(0.8 이상) 교과서 단어일 때만 (예문에 쓴 yesterday 하나로 "Unit14" 라고 하지 않게)
        note_unit = None
        for u in used:
            if u.startswith("R-"):
                r = golden.find_rule(u); note_unit = (r or {}).get("unit"); break
            if u.startswith(("F-", "p-")):
                note_unit = unit_of.get(u) or _textbook_index()["by_id"].get(u, (None, None, None))[2]; break
        if note_unit is None and ratio >= 0.8:
            counts: dict[str, int] = {}
            for u in hit_units:
                if u and u != "ALL":
                    counts[u] = counts.get(u, 0) + 1
            note_unit = max(counts, key=counts.get) if counts else None
        if from_textbook and note_unit and note_unit != "ALL" and ctx.unit and note_unit != ctx.unit:
            answer = f"{note_unit}에서 배우는 내용이에요. {answer}"
        elif not from_textbook and has_english and bool(out.get("own_knowledge")):   # 자료 밖의 영어 지식 답에만 표시 (화면 상황·오답노트·인사 답엔 안 붙임)
            answer = _OUT_OF_TEXTBOOK_PREFIX + answer
    rule_ids = [u for u in used if u.startswith("R-")]
    for u in used:
        rule_ids += faq_rules.get(u, [])
    suggested = _followup_questions(list(dict.fromkeys(rule_ids)), golden.faqs()) if rule_ids else []
    return {"answer": answer, "source": [{"chunk_id": u} for u in used[:6]], "offtopic": offtopic, "suggested": suggested,
            "from_textbook": from_textbook, "coverage": round(ratio, 2), "llm": out.get("_llm")}
