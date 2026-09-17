"""
물어보기 챗 (PRD 4.4, 화면/통합은 팀장 소관 · 백엔드가 아직 없어서 TTS 담당이 임시로 준비)

POST /api/ask
body: {"student", "question", "context": {"screen","unit","rule_id","log_id","text","source","level"}}
→ {"answer", "source": [{"chunk_id"}], "offtopic", "suggested": [...]}
(common.js 의 askChat() 이 이미 이 형식을 기다림 — 필드 바꾸면 그쪽도 같이 바꿔야 함)

ask() → _hybrid_answer()(계약 문서 2-2절, TTS 담당 수정 목록 1번, 2026-09-16 연결):
1) 결정적 예외처리 + 로컬 매칭(faq.jsonl→rules.jsonl→patterns→words, 단어 겹침) 먼저 —
   되면 LLM 호출 없이 즉시 반환
2) 안 되면 검색 기반 _retrieval_answer()로 — search_faq/search_rule_aliases/search_textbook이
   후보를 좁히고, 그 안에서만 LLM이 답을 지음(옛 "FAQ 전체를 프롬프트에 넣고 고르게 함" 폴백은
   삭제됨)

context.log_id 가 있으면 sentence_log.jsonl 에서 그 순간의 원문·고친 문장을 찾아 프롬프트에
넣는다("아까 말한 거 고쳐줘"에 다시 추론 안 하고 /fix 결과를 그대로 씀). student.py 의
notebook_text() 도 개인화 참고 자료로 넣는다(답 근거는 여전히 FAQ).

매 질문·답변을 chat_log.jsonl 에 기록해뒀다가, 같은 학생이 CHAT_HISTORY_WINDOW_SEC 이내에
또 물어보면 최근 대화를 프롬프트에 같이 줘서 "그거/이거" 같은 지시어를 이해하게 한다
(프론트가 대화 기록을 안 보내도 서버가 student+시간 윈도우로 알아서 판단, 2026-09-10).
"""
import difflib
import json
import math
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


def _ira_neun(text: str) -> str:
    """"'{뜻}'라는 뜻이에요"에 쓸 조사. 받침 있으면 "이라는", 없으면 "라는"(예: "가족'이라는" vs
    "버스'라는") — 지금까지 "라는"으로 고정돼 있어서 받침 있는 뜻(교재 단어 400개 중 224개,
    2026-09-16 실측)의 절반 이상이 문법 오류로 나가고 있었다."""
    ch = text.strip()[-1] if text.strip() else ""
    if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0:
        return "이라는"
    return "라는"


def _norm_words(text: str) -> list[str]:
    # "make+목적어+형용사가"처럼 "+"/"/"로 붙은 단어가 공백 split()으론 하나로 뭉쳐서, _best_match의
    # "후보 단어 2개 이상인데 1개만 겹치면 스킵" 안전장치를 우연히 피해가는 문제가 있었음(2026-09-11,
    # "형용사 앞에 뭐가 와요?"가 무관한 FAQ에 1.0 점수로 매칭됨) — "+"/"/"도 구분자로 취급해 쪼갠다.
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


def _fuzzy_rule_name_match(question: str, rule: dict, threshold: float = 0.6) -> bool:
    """편집거리(difflib)로 질문의 내용어와 규칙 이름(type/short)이 충분히 가까운지 본다 —
    _overlaps_question의 "접두 2글자 일치" 조건은 첫 글자가 오타면(과→괴) 못 잡는다.
    type의 "(시간)" 같은 괄호 설명은 떼고 비교(안 떼면 진짜 정답도 0.6대 초반이라 문턱을
    넘기 어려움). 임계값 0.6은 실측 기준 — "미래시제"·"과거시제"처럼 진짜 다른 규칙끼리는
    0.44 밖에 안 나오고, "괴거시제"·"과거시제"는 0.667이라 그 사이에 안전하게 걸린다."""
    labels = [_PAREN.sub("", rule.get("type") or ""), _PAREN.sub("", rule.get("short") or "")]
    for w in _content_words(question):
        if len(w) < 3:
            continue
        for label in labels:
            if label and difflib.SequenceMatcher(None, w, label).ratio() >= threshold:
                return True
    return False


# "elephant는 a예요 an이에요?"류 질문 — LLM한테 맡겼더니 "elephant는 자음이라 a"처럼 기본
# 문법을 틀리게 답한 사례가 있어서(2026-09-14), 교재 어휘 기준으로 결정적으로 답한다. 소리가
# 철자와 다른 예외(uniform=자음 소리, hour=모음 소리)는 golden 어휘 전체를 훑어서 확인한 것만
# 등록 — 이 밖의 예외는 모르니 답하지 않는다(아래 함수가 None 반환).
_A_AN_EXCEPTIONS = {"uniform": "a", "hour": "an"}
# "an이에요 a예요?"처럼 an을 먼저 의심하고 되짚어 묻는 순서도 있어서(2026-09-16 지적 — 기존엔
# a→an 순서만 잡아서 이 어순은 그냥 검색으로 새고 있었음, 이 핸들러를 만든 이유 자체가 LLM이
# 기본 문법을 틀리는 걸 막기 위해서라 여기서 놓치면 다시 그 위험에 노출됨) 양쪽 어순 다 잡는다.
_A_AN_Q = re.compile(
    r"([A-Za-z]+)[가-힣]{0,3}\s*(?:"
    r"a\s*(?:예요|인가요|써요|이에요)?\s*an\s*(?:이에요|인가요|써요|예요)?"
    r"|an\s*(?:이에요|인가요|써요|예요)?\s*a\s*(?:예요|인가요|써요|이에요)?"
    r")"
)


def _a_an_word_answer(word: str) -> dict:
    lw = word.lower()
    article = _A_AN_EXCEPTIONS.get(lw, "an" if lw[:1] in "aeiou" else "a")
    sound = "모음" if article == "an" else "자음"
    return {"answer": f'{word}는 {sound} 소리로 시작해서 "{article} {word}"가 맞아요.',
            "source": [{"chunk_id": "R-34"}], "offtopic": False, "suggested": []}


def _a_an_answer(question: str) -> dict | None:
    m = _A_AN_Q.search(question)
    if not m:
        return None
    word = m.group(1)
    if word.lower() in ("a", "an"):
        return None
    return _a_an_word_answer(word)


# "elephant는 a예요 an이에요?" 다음에 "uniform은요?"처럼 단어만 바꿔 짧게 묻는 후속 질문 —
# 그 자체로는 a/an 질문인지 알 수 없어서(2026-09-14, "uniform은요?"가 단어 뜻 설명으로,
# "hour는요?"가 아예 offtopic으로 샌 것 확인), 직전 대화가 진짜 a/an 규칙(R-34)에 근거했을
# 때만 같은 방식으로 이어서 답한다.
_A_AN_FOLLOWUP_Q = re.compile(r"^([A-Za-z]+)[는은]\s*(요)?\s*\??$")


def _a_an_followup_answer(question: str, student: str) -> dict | None:
    m = _A_AN_FOLLOWUP_Q.match(question.strip())
    if not m:
        return None
    last = next((t for t in reversed(_recent_chat_turns(student, max_turns=5)) if t.get("rule_ids")), None)
    if not last or "R-34" not in last["rule_ids"]:
        return None
    return _a_an_word_answer(m.group(1))


def _corpus_idf(items: list[dict], candidates_of) -> dict[str, float]:
    """이 후보 집합(FAQ 전체 또는 규칙 전체) 안에서 각 내용어의 문서빈도(df, 몇 개의 서로 다른
    후보에 등장하는지) 기반 가중치 — 표준 IDF(log(N/df))와 같은 발상. "왜"/"앞에"처럼 여러
    FAQ에 공통으로 나오는 질문 틀 상투어는 df가 커서 가중치가 자동으로 낮아지고, 특정 FAQ
    한둘에만 나오는 진짜 주제어는 가중치가 높게 유지된다 — _GENERIC_WORDS를 새로 발견할 때마다
    손으로 계속 늘리는 대신(2026-09-17, "왜 do를 you 앞에 써야 해?"가 "왜"·"앞에"만 겹쳐 무관한
    F-06에 0.5로 매칭되던 문제로 발견 — 그 둘은 _GENERIC_WORDS에 없었음), 말뭉치 통계로 새 상투어도
    자동으로 걸러지게 한다. _GENERIC_WORDS는 그대로 두고(이미 검증된 안전장치) 이건 보조 계층이다."""
    df: dict[str, int] = {}
    for item in items:
        seen: set[str] = set()
        for cand in candidates_of(item):
            seen |= set(_content_words(cand))
        for w in seen:
            df[w] = df.get(w, 0) + 1
    n = max(len(items), 1)
    return {w: max(math.log(n / d), 0.1) for w, d in df.items()}   # 모든 후보에 다 나오는 단어(d==n)도
                                                                     # 0이 아니라 최소 가중치는 남긴다


def _best_match(question: str, items: list[dict], candidates_of) -> tuple[dict | None, float]:
    """단어 겹침 기반 매칭. frontend/js/common.js 의 faqMatch()와 같은 알고리즘(단, IDF 가중치는
    아직 거기 없음) — 서버가 먼저 이걸로 찾아보고, 못 찾을 때만 Gemini 로 넘어간다(할당량 절약,
    응답도 빠름)."""
    qs = _content_words(question)
    idf = _corpus_idf(items, candidates_of)
    best, best_score = None, 0.0
    for item in items:
        for cand in candidates_of(item):
            cs = _content_words(cand)
            if not cs:
                continue
            # 부분 문자열 겹침은 두 단어 다 3글자 이상이고 길이 차가 2 이하일 때만 인정 — 2글자는 "an"이
            # "elephant"의 부분 문자열이라 무관한 단어끼리 겹치는 경우가 있고(2026-09-10), 길이 차가
            # 크면 "the"가 "weather" 안에, "get"이 "budget"이 안에 우연히 들어있는 것처럼 무관한 단어끼리
            # 겹치는 경우가 있음(2026-09-14). 완전히 같은 단어는 길이 상관없이 인정.
            hit_words = {w for w in cs if any(
                w == x or (len(w) >= 3 and len(x) >= 3 and abs(len(w) - len(x)) <= 2 and (w in x or x in w))
                for x in qs
            )}
            if len(cs) >= 2 and len(hit_words) < 2:
                continue   # 단어 2개 이상인 후보가 1개만 겹치면 우연의 일치로 보고 스킵 — "과거형이 뭐에요?"가
                           # "see 과거형"과 "과거형" 한 단어만 겹쳐 saw 전용 FAQ로 잘못 매칭되던 문제(2026-09-10)
            weighted_total = sum(idf.get(w, 1.0) for w in cs)
            score = sum(idf.get(w, 1.0) for w in hit_words) / weighted_total if weighted_total else 0.0
            if score > best_score:
                best_score, best = score, item
    return best, best_score


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


def _word_answer(entry: dict, note: str = "", ctx_unit: str | None = None, level: int = DEFAULT_LEVEL) -> dict:
    # lookup_word() 결과는 unit을 담고 있어서(_word_match의 words_pool엔 없음 — golden.all_words()가
    # unit을 안 줌), 여기서만 다른 유닛 안내를 붙일 수 있다. 패턴·단어 임베딩 검색+LLM 생성 경로가
    # 이미 이 안내를 쓰고 있는 것과 통일(2026-09-16 발견 — 단어 조회만 조용히 답하고 있었음).
    # "ALL"(유닛 무관 공통 자료)은 불일치로 안 본다.
    unit_note = (f"{entry['unit']}에서 배우는 내용이에요. "
                 if ctx_unit and entry.get("unit") and entry["unit"] not in (ctx_unit, "ALL") else "")
    answer = f"{unit_note}{note}{entry['word']}는 '{entry['meaning']}'{_ira_neun(entry['meaning'])} 뜻이에요."
    if entry.get("example"):
        answer += f" 예: {entry['example']}"
    # 단어 조회는 가장 흔한 질문 유형인데 suggested가 항상 비어있었다(2026-09-16 발견) — 같은
    # 유닛의 교과서 패턴 하나를 추천 질문으로 준다. _word_match(words_pool)의 항목엔 unit이
    # 없어서(golden.all_words()가 안 줌) 그 경로는 자연히 그대로 빈 채로 남는다. "다른 예문
    # 보여줘"류 이어가기 문구는 일부러 안 쓴다 — 이 답의 source가 []라(단어엔 rule_id가 없음)
    # _referential_rule_answer가 직전 맥락을 못 찾아 엉뚱한 FAQ로 새는 문제(2026-09-16 실사용
    # 테스트에서 재현)가 있어서, 검색 없이 바로 답 가능한 새 질문만 추천한다.
    suggested = []
    if entry.get("unit"):
        try:
            patterns = golden.patterns(entry.get("level") or level, entry["unit"])
            # words.csv·patterns.csv가 같은 교재 문장을 id만 다르게(w-0081/p-0081) 담아둔 경우가
            # 있어서, 방금 답의 예문과 똑같은 패턴을 또 추천하지 않게 다음 걸로 넘어간다.
            pat = next((p for p in patterns if p["text"] != entry.get("example")), None)
            if pat:
                suggested = [f"{pat['text']} 무슨 뜻이에요?"]
        except Exception:
            pass
    return {"answer": answer, "source": [], "offtopic": False, "suggested": suggested}


def _word_match(question: str, words_pool: dict[str, dict]) -> dict | None:
    """질문에 등장한 영단어가 words.csv(교재 어휘 전체, ~400개)에 정확히 있으면 그 뜻으로 답한다.
    FAQ에 없는 대다수 교재 단어(예: play)가 계속 offtopic 처리되던 걸 확인해서 추가(2026-09-10)."""
    eng_words = re.findall(r"[A-Za-z']+", question)
    for w in eng_words:
        entry = words_pool.get(w.lower())
        if entry:
            return _word_answer(entry)

    # 정확히 못 찾으면 오타로 보고 tutor.py가 이미 만들어둔 철자 사전을 재사용해 교정 시도
    # (2026-09-14 — "pencl이 뭐예요?"가 지금까지 그냥 offtopic으로 빠지던 문제, ask.py엔 철자
    # 교정이 아예 없었음. tutor.py 파일 자체는 안 건드리고 함수만 읽기 전용으로 재사용).
    try:
        from backend.tutor import _spell
        sp = _spell()
    except Exception:
        sp = None
    if sp:
        for w in eng_words:
            lw = w.lower()
            if lw in words_pool or len(lw) < 3:
                continue
            fixed = sp.correction(lw)
            if fixed and fixed != lw and fixed in words_pool:
                return _word_answer(words_pool[fixed], note=f"혹시 {words_pool[fixed]['word']}를 말씀하신 거죠? ")
    return None


def _pattern_match(question: str, patterns_pool: list[dict], faq_list: list[dict]) -> dict | None:
    """질문 문장이 patterns.csv(교재 예문 전체)와 크게 겹치면 그 뜻으로 답한다(예: "Good night!")."""
    best, best_score = _best_match(question, patterns_pool, lambda p: [p["text"]])
    if best_score < 0.6:
        return None
    rule_ids = [best["rule_id"]] if best.get("rule_id") else []
    return {"answer": f"{best['text']}는 '{best['meaning']}'{_ira_neun(best['meaning'])} 뜻이에요.",
            "source": [{"chunk_id": rid} for rid in rule_ids], "offtopic": False,
            "suggested": _followup_questions(rule_ids, faq_list)}


def _local_match(question: str, faq_list: list[dict], rule_list: list[dict],
                  words_pool: dict[str, dict], patterns_pool: list[dict], level: int = 3,
                  ctx_unit: str | None = None, skip_word_lookup: bool = False) -> dict | None:
    """faq→rules→patterns→words 순으로 로컬 매칭, 전부 실패하면 None → 폴백.

    level: 단어장 조회(lookup_word)에 쓸 학년. _retrieval_answer()가 실패 시 같은 조회를 또
    하지 않도록(skip_word_lookup) 여기서도 _retrieval_answer()와 같은 값(ctx.level or
    DEFAULT_LEVEL)을 받아써서 두 곳의 lookup_word 결과가 어긋나지 않게 한다(2026-09-16).

    ctx_unit: 단어 조회(lookup_word) 결과가 다른 유닛 것이면 안내를 붙이는 데만 씀
    (_word_answer 참고). FAQ·규칙 단어겹침·패턴 매칭(바로 아래)은 일부러 안 붙였다 — 그
    셋은 원본 데이터 자체에 unit이 있어서 붙이는 건 가능하지만(2026-09-16 확인), FAQ 130개·
    규칙 100개가 유닛 20개+ALL에 5~8개씩 흩어져 있어 "지금 유닛과 같을 확률"이 5~10%뿐이라,
    붙이면 매칭 성공 시 거의 매번(90%+) 뜨는 상투어가 돼서 오히려 안내의 의미가 옅어진다.
    단어 조회만 먼저 통일하고, FAQ·규칙·패턴까지 넓힐지는 실사용 데이터 더 보고 결정하기로 함.

    RAG 힌트로 불일치를 진단 로그로만 남기던 코드는 삭제함(2026-09-16) — 1단계가 성공한 답마다
    임베딩을 한 번 더 호출해 서버 상태에 좌우되게 만들었는데, 정작 그 힌트가 맞았던 적은
    24번 중 1번뿐이라(2026-09-11 실측, [[project_rag_rerank_ensemble_findings]]) 답에도 전혀
    안 쓰였다 — 1단계의 "서버 없이도 동작" 이라는 목적과 맞지 않아 정리."""
    faq, faq_score = _best_match(question, faq_list, lambda f: [f["question"]] + (f.get("variants") or []))
    if faq_score >= 0.5:
        faq_rule_ids = faq.get("rule_ids") or []
        source = [{"chunk_id": rid} for rid in faq_rule_ids] + [{"chunk_id": faq["id"]}]
        suggested = _followup_questions(faq_rule_ids, faq_list, exclude_id=faq["id"])
        return {"answer": faq["answer"], "source": source, "offtopic": False, "suggested": suggested}

    rule, rule_score = _best_match(question, rule_list, lambda r: [r["type"], r.get("short", "")])
    if rule_score >= 0.5:
        # rule["short"]는 UI 라벨용 압축 태그라("숫자 2 이상+복수형") 챗봇 답으로 그대로 쓰면
        # 문장이 아니라 조각처럼 끝남(2026-09-14 재현, "형용사는 명사 앞에") — 완전한 설명
        # 문장인 rule["text"]를 쓴다.
        return {"answer": rule["text"], "source": [{"chunk_id": rule["id"]}],
                "offtopic": False, "suggested": _followup_questions([rule["id"]], faq_list)}

    # 패턴(전체 문장) 매칭을 단어 매칭보다 먼저 본다 — "Good night!"가 그 안의 "night" 단어
    # 매칭에 먼저 걸려버리면 더 정확한 문장 전체 뜻 대신 단어 하나 뜻만 나오는 문제가 있었음(2026-09-10)
    pattern = _pattern_match(question, patterns_pool, faq_list)
    if pattern:
        return pattern

    # 단어 하나만 겹쳐서 잡히는 게 원래 목적("play가 무슨 뜻이야?")인데, 영단어가 여러 개
    # 섞인 질문("I want a doctor 이거랑 I want to be a doctor 뭐가 달라요?")도 그중 하나만
    # 걸려서 문장 비교 대신 단어 뜻풀이로 잘못 답하던 문제(2026-09-11) — RAG 힌트로 걸러보려
    # 했으나 점수 자체가 신뢰하기엔 너무 자주 틀려서(단순 단어 질문에도 0.83으로 확신) 대신
    # 질문에 영단어가 2개를 넘으면(비교·복문 가능성) 단어 매칭을 건너뛰고 LLM 폴백으로 넘긴다.
    if len(re.findall(r"[A-Za-z']+", question)) <= 2 and not skip_word_lookup:
        # 계약 문서(2026-09-15) — 영어→뜻은 lookup_word()로 대체(한국어→영어 역방향도 덤으로
        # 지원). 단, lookup_word의 한국어 뜻 매칭은 순수 부분일치라 "형"이 "과거형/형용사"
        # 안에도 걸리는 오탐이 있어서(2026-09-16 재현) _retrieval_answer()와 같은 안전장치를
        # 그대로 쓴다: 영어 낱말이 질문에 그대로 있거나 "영어로" 표시가 있을 때만 신뢰.
        from backend import textbook
        hits = textbook.lookup_word(question, level=level)
        if hits and not _PROPERTY_TAIL.search(question):
            w = hits[0]
            eng_in_q = w["word"].lower() in question.lower()
            asks_translation = bool(re.search(r"영어로|영어\s*(단어|낱말)", question))
            if eng_in_q or asks_translation:
                return _word_answer(w, ctx_unit=ctx_unit, level=level)
        # lookup_word가 못 찾으면 오타로 보고 _word_match의 스펠체커 폴백을 재사용(lookup_word엔
        # 오타 교정이 없음 — "-s/-es/-ing/-ed" 어미 제거만 함, "pencl" 같은 오타는 못 잡음). 이것도
        # "과거형"류 속성 질문이면 건너뛴다 — _word_match엔 원래 속성 판별이 아예 없어서 "play
        # 과거형이 뭐야"가 뜻풀이로 새고 있었다(2026-09-17 발견).
        word = None if _PROPERTY_TAIL.search(question) else _word_match(question, words_pool)
        if word is not None:
            return word

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

# "그거 예문 더 보여줘"처럼 방금 대화를 가리키는 지시어 — _local_match의 FAQ/규칙 단어겹침이
# 먼저 걸려서 "예문"/"보여줘" 같은 흔한 단어로 무관한 항목을 확정 답변해버리는 문제가 있었음
# (2026-09-11) — 검색 없이 직전 규칙 문서로 바로 답하게 아래 _referential_rule_answer()를 둠.
_REFERENTIAL_PATTERN = re.compile(
    r"그거|그것|이거|이것|왜\s*그래|그렇게|"
    r"예문.{0,6}(더|다른|또)|(더|다른|또).{0,6}예문|"  # "다른 예문 있어?"도 방금 대화 이어가기(2026-09-11)
    r"다시\s*설명|더\s*쉽게|쉽게\s*다시|"   # "더 쉽게 설명해줘"도 방금 대화 이어가기인데 offtopic으로
                                          # 거절되던 문제(2026-09-14, "형용사 앞에 뭐가 와요?" 직후 재현)
    r"^왜\s*요?\s*\??$"   # "왜요?"/"왜?"만 짧게 물으면 "왜 그래"가 아니라서 안 걸리던 문제
                          # (2026-09-14, can 이유 설명 직후 "왜요?"가 offtopic으로 빠짐). 새 주제를
                          # 담은 긴 "왜 X는 Y해요?"는 이 패턴에 안 걸려서 정상적으로 규칙 검색됨.
)

# "X랑 Y 뭐가 달라?"/"X 랑 Y 뭔 차이야?"류 비교 질문 — STT가 "뭐가 달라요"를 "모가달라요"로
# 흘려써도 "달라" 부분문자열은 남아서 여전히 걸린다(2026-09-17, hybrid_stt 실측 확인).
_COMPARE_PATTERN = re.compile(r"차이|다르|달라")

_DEFINE_TAIL = re.compile(r"뭐(예요|야|지|임)|무슨\s*뜻|뜻이\s*뭐|뜻인가요")

# "과거형이 뭐야"/"복수형이 뭐예요"류 — 단어의 "뜻"이 아니라 특정 문법 속성을 물은 질문. 이게
# 있으면 단어장 조회(lookup_word, 뜻풀이)로 바로 답하면 안 되고(2026-09-17, "play 과거형이 뭐야"가
# "play는 논다는 뜻이에요"로, "cook 과거형이 뭐예요?"가 "cook는 요리사라는 뜻이에요"로 질문과
# 무관하게 답해버리던 문제 발견), _word_pair_rule_answer()가 규칙을 찾을 때도 그 규칙 본문에
# 같은 속성 키워드가 실제로 있어야만 인정해야 한다("walk 과거형이 뭐야"가 walk를 예문에만 우연히
# 담은 R-28(too+형용사, "과거형" 언급 전혀 없음)을 근거로 대던 문제 발견).
_PROPERTY_TAIL = re.compile(r"과거형|복수형|현재형|미래형|스펠링|철자")

# "go랑 went 뭐가 달라?"/"foot이랑 feet이랑 뭐가 달라?"류 질문에서 규칙 본문 매칭에 쓸 때 무시할
# 흔한 문법 기능어 — 이 단어들만 우연히 겹쳐서 엉뚱한 규칙이 걸리는 걸 막는다(예: "want가 뭐예요?"가
# want를 언급하는 규칙 10개+에 다 걸려 모호해지는 것 방지).
_RULE_MATCH_STOPWORDS = {
    "this", "that", "these", "those", "have", "has", "want", "wants", "like", "likes",
    "make", "makes", "here", "there", "very", "also", "too", "how", "what", "who", "why",
    "each", "every", "some", "any", "many", "much", "day", "school", "time", "good", "well",
    # go/went 같은 2글자 실질단어(go, on, in, up 등)까지 살리려고 길이 기준을 2로 낮췄는데,
    # 그러면 흔한 2글자 문법 기능어까지 같이 들어와서 따로 뺀다(2026-09-17).
    "is", "am", "be", "an", "to", "at", "in", "on", "up", "it", "we", "he", "my", "no",
    "so", "do", "of", "or", "if", "us", "as", "the", "and",
}


def _rule_text_words(rule: dict) -> set[str]:
    text = " ".join([rule.get("text", ""), " ".join(rule.get("examples") or []), rule.get("wrong_example") or ""])
    return {w.lower() for w in re.findall(r"[A-Za-z']+", text) if len(w) >= 2} - _RULE_MATCH_STOPWORDS


# 규칙 text는 관례상 "한국어 설명. (예:/틀린 예: 또는 그냥) 영어 예문들" 순서로 쓰여있어서, 설명
# 문장(preamble)만 잘라내면 "그 규칙이 실제로 설명하는 단어"와 "예문에 우연히 등장한 단어"를
# 가를 수 있다 — "예:"/"틀린 예:" 표시나 ". 대문자" 문장 경계 중 가장 먼저 나오는 지점에서 자른다.
_PREAMBLE_CUT = re.compile(r"틀린\s*예\s*:|예\s*:|\.\s+[A-Z]")


def _rule_preamble_words(rule: dict) -> set[str]:
    text = rule.get("text", "")
    m = _PREAMBLE_CUT.search(text)
    preamble = text[:m.start()] if m else text
    return {w.lower() for w in re.findall(r"[A-Za-z']+", preamble) if len(w) >= 2} - _RULE_MATCH_STOPWORDS


def _word_pair_rule_answer(question: str) -> dict | None:
    """"go랑 went 뭐가 달라?"류 비교 질문(과 "went가 뭐예요?"류 한 단어 질문)이 임베딩 검색에
    안 걸려 offtopic으로 새던 문제(2026-09-17 실사용 테스트 발견 — R-31은 rule_alias_hits 상위
    3위 안에도 안 들어오고, FAQ도 "buy 과거형"(F-125)만 있고 go/see/eat용은 없음)를, 사람이
    "go/went" 같은 쌍을 미리 표로 나열하는 대신 규칙 본문(text/examples/wrong_example)에 그
    단어들이 실제로 같이 나오는지 그때그때 찾아서 잡는다 — 새 규칙이 추가돼도 코드 수정 없이
    자동으로 커버된다(2026-09-17, R-71의 foot/feet·tooth/teeth도 같은 문제라 이렇게 일반화함).

    _retrieval_answer()의 다른 모든 경로(FAQ·규칙별칭·패턴·단어)가 전부 실패한 뒤 "5) 전부 실패"
    직전에만 최후 수단으로 호출된다 — 이미 더 정교하게 튜닝된 FAQ 답변(예: buy/bought의 F-125)이
    있으면 그게 먼저 이기고, 이 함수는 아무 데도 안 걸렸을 때만 한 번 더 찾아보는 안전망이다.

    먼저 설명 문장(preamble)만으로 찾아본다 — "ate가 뭐예요?"가 R-31(진짜 설명: "eat는 ate가
    돼요")·R-34·R-53(둘 다 예문에만 ate가 우연히 등장) 세 규칙에 다 걸려 모호해지던 문제를
    이걸로 가른다(2026-09-17). 그래도 못 찾으면 예문까지 넓혀서 재시도한다.

    비교 질문("X랑 Y")은 두 단어가 다 같은 규칙에 있어야 하니 모호할 위험이 낮아 정확히 하나일
    때만 답하고, 한 단어만 묻는 질문은 그 단어가 데이터에 있다는 가정하에(2026-09-17 사용자 결정)
    — 그래도 여러 규칙에 걸치면 첫 번째로 답한다(안 맞는 규칙이라도 완전히 무시하고 offtopic
    처리하는 것보단 낫다고 보고)."""
    q_words = {w.lower() for w in re.findall(r"[A-Za-z']+", question) if len(w) >= 2} - _RULE_MATCH_STOPWORDS
    if not q_words:
        return None
    is_compare = bool(_COMPARE_PATTERN.search(question)) and len(q_words) >= 2
    is_define = bool(_DEFINE_TAIL.search(question))
    if not (is_compare or is_define):
        return None

    def _find(word_fn):
        found = []
        for rule in golden.rules():
            rule_words = word_fn(rule)
            if is_compare:
                if q_words <= rule_words:
                    found.append(rule)
            elif q_words & rule_words:
                found.append(rule)
        return found

    hits = _find(_rule_preamble_words) or _find(_rule_text_words)
    property_kw = _PROPERTY_TAIL.findall(question)
    if property_kw:
        # "과거형"을 물었으면 단어만 우연히 겹치는 게 아니라 매칭된 규칙 본문에도 실제로 그
        # 속성 단어가 있어야 인정한다 — "walk 과거형이 뭐야"가 walk를 예문에만 담은 R-28(too+
        # 형용사, "과거형" 언급 전혀 없음)을 근거로 대던 문제(2026-09-17 발견)를 막는다.
        hits = [r for r in hits if any(kw in r.get("text", "") for kw in property_kw)]
    if not hits:
        return None
    if is_compare and len(hits) != 1:
        return None  # 비교 질문은 정확히 하나로 좁혀질 때만 — 어느 쪽을 비교하는지 틀리면 안 되니
    rule = hits[0]  # 한 단어만 묻는 질문은 여러 규칙에 걸쳐도 첫 번째로 답한다(위 docstring 참고)
    return {"answer": rule["text"], "source": [{"chunk_id": rule["id"]}], "offtopic": False,
            "suggested": _followup_questions([rule["id"]], golden.faqs())}


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
    """"비슷한 게 있을까요?" 류 요청을 정규식으로 미리 잡아 LLM 호출 없이 처리한다(빠른 경로).
    정규식이 못 잡는 표현은 여기서 놓치고 아래 검색 기반 경로(_retrieval_answer)로 넘어간다."""
    if not _SIMILAR_PATTERN.search(question):
        return None
    return _alternative_response(student, faq_list)


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

    level: RETRIEVAL_PROMPT처럼 페르소나 문구("초등학교 N학년")에만 씀 — 이전엔 "3~4학년"으로
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
    result = _hybrid_answer(body)
    _log_chat_turn(body.student, body.question.strip(), result.get("answer", ""), result.get("source"))
    return result


# 어간 "틀리"를 넣어서 틀리는/틀리나요/틀리죠/틀리지 등을 한 번에 잡는다 — "틀림"(명사형, "나 뭐
# 자주 틀림?")은 "틀리"가 그 안에 부분문자열로도 안 들어있어서(한글 음절 "리"≠"림") 별도로
# 추가해야 했다(2026-09-16 실사용 테스트에서 재현 — 이 표현만 트리거가 아예 안 걸렸음).
_NOTEBOOK_TRIGGER = re.compile(r"틀렸|틀린|틀려|틀림|틀리|오답|실수")
_TRAILING_PARTICLE = re.compile(r"(는|은|이|가|을|를|도|만|의|랑|와|과|에서|에게|에)$")
# "내가 뭘 자주 틀려?"의 "자주"처럼 진짜 문법 주제가 아니라 오답노트 질문에 흔히 붙는 부사 —
# topic_words에 남으면 "구체적 주제를 물었다"고 오판해서 요약 답변이 안 나가게 된다(2026-09-16
# _notebook_summary_answer 추가하면서 발견). "요즘 계속"/"맨날"처럼 이런 부사가 두 개 겹치면
# 내용어 개수(3개 이하) 문턱까지 넘겨버려서 아예 거절되는 문제도 있어서(2026-09-16 실사용
# 테스트 재발견) _notebook_content_word_count()에서도 이 집합을 뺀다.
_NOTEBOOK_FILLER_WORDS = {"자주", "자꾸", "요즘", "가끔", "맨날", "만날", "매번", "계속", "여전히", "아직도"}


def _notebook_content_word_count(question: str) -> int:
    """오답노트 질문이 "막연한지 구체적인지" 가르는 내용어 개수 — "요즘"/"자꾸" 같은 흔한 부사는
    구체적 주제가 아니므로 안 센다."""
    return len([w for w in _content_words(question) if w not in _NOTEBOOK_FILLER_WORDS])


def _notebook_rule_answer(question: str, student: str) -> dict | None:
    """"내가 관사를 틀렸었나?"처럼 오답노트 질문에 구체적 문법 주제가 있으면, notebook_text() 전체
    요약을 LLM에 던져 텍스트 생김새로 아무 줄이나 고르게 하는 대신(2026-09-14 재현 — "관사"를
    물었는데 실제 관사 규칙(R-38, "I saw a dog") 대신, 우연히 "a"가 붙어 있는 다른 규칙(R-08)의
    예문을 잘못 골라 답함), 그 학생 오답노트에서 이름이 실제로 일치하는 규칙 하나를 찾아
    결정적으로 답한다. 일치하는 게 없으면 None(기존 경로로 폴백)."""
    if not _NOTEBOOK_TRIGGER.search(question):
        return None
    topic_words = [_TRAILING_PARTICLE.sub("", w) for w in _content_words(question)]
    topic_words = [w for w in topic_words if len(w) >= 2 and not _NOTEBOOK_TRIGGER.search(w)]
    if not topic_words:
        return None
    from backend.student import notebook_summary
    book = notebook_summary(student, max_examples=1)
    for it in book["active"] + book["overcome"]:
        # "인사말이야?"처럼 조사가 아니라 서술격 어미("-이야")가 붙으면 위 particle-strip으로 못
        # 떼지는데, 규칙 이름("인사말 문장부호")을 단어 단위로 쪼개 양방향 부분일치로 잡는다.
        name_words = [nw for nw in re.split(r"[\s()·]+", it["name"]) if len(nw) >= 2]
        if not any(w in nw or nw in w for w in topic_words for nw in name_words):
            continue
        ex = it["examples"][0] if it.get("examples") else None
        answer = f"네, {it['name']}({it['rule_id']}) 부분을 {it['count']}번 틀렸어요."
        if ex:
            answer += f" 예를 들어 '{ex['text']}'는 '{ex['fixed']}'로 고쳐야 해요."
        return {"answer": answer, "source": [{"chunk_id": it["rule_id"]}], "offtopic": False, "suggested": []}
    return None


def _notebook_summary_answer(question: str, student: str) -> dict | None:
    """"내가 뭘 자주 틀려?"/"틀린 거 알려줘"처럼 특정 문법 주제 없이 오답노트 전체를 요약해
    달라는 질문 — _notebook_rule_answer()는 주제어가 없으면(topic_words 없음) None을 반환해서
    이런 질문이 그냥 일반 검색으로 새 "그건 교과서에 없어요"로 거절되고 있었다(2026-09-16
    오답노트 화면 실사용 테스트에서 재현 — 계약 문서 2-1절이 오답노트 화면 예시 질문으로 바로
    이 문장을 들고 있는데도 안 됐음). 옛 _answer()의 PROMPT 5번 규칙이 LLM에게 자유 요약을
    맡겼던 걸(2026-09-16 삭제 전 확인), 지금 결정적 매칭 기조에 맞춰 notebook_summary()로 직접
    만든다 — 아직 안 극복한(overcome 제외) 규칙 중 많이 틀린 순으로 최대 2개, 그 중 1위는
    최근 예문도 같이.

    "관계대명사 틀렸었나?"처럼 구체적 주제를 짚었는데 그 학생이 실제론 안 틀린 경우(_notebook_
    rule_answer가 이름 매칭에 실패해 여기로 넘어옴), 조용히 다른 주제(top-2 요약)로 답을 바꿔치기
    하면 학생이 자기가 물어본 주제에 답을 들었다고 착각한다(2026-09-16 실사용 테스트에서 재현).
    _notebook_rule_answer와 같은 방식으로 topic_words를 다시 뽑아, 구체적 주제가 있었으면 정직하게
    "기록에 없다"고 답하고, 진짜 막연한 질문(topic_words 없음)일 때만 top-2 요약을 준다."""
    if not _NOTEBOOK_TRIGGER.search(question) or _notebook_content_word_count(question) > 3:
        return None
    topic_words = [_TRAILING_PARTICLE.sub("", w) for w in _content_words(question)]
    topic_words = [w for w in topic_words if len(w) >= 2 and not _NOTEBOOK_TRIGGER.search(w)
                   and w not in _NOTEBOOK_FILLER_WORDS]
    if topic_words:
        return {"answer": "그 부분은 아직 오답노트에 없어요. 문제를 몇 개 더 풀어보면 알 수 있을 거예요!",
                "source": [], "offtopic": False, "suggested": []}
    from backend.student import notebook_summary
    items = sorted(notebook_summary(student, max_examples=1)["active"],
                   key=lambda it: it["count"], reverse=True)[:2]
    if not items:
        return None
    answer = ", ".join(f"{it['name']}({it['rule_id']})을(를) {it['count']}번" for it in items) + " 틀렸어요."
    top_ex = items[0]["examples"][0] if items[0].get("examples") else None
    if top_ex:
        answer += f" 예를 들어 '{top_ex['text']}'는 '{top_ex['fixed']}'로 고쳐야 해요."
    # 여러 규칙을 한 번에 요약했으니, 이어지는 "이거 왜 틀렸어?" 류가 어느 걸 가리키는지 모호해서
    # _referential_rule_answer()가 되묻게 되는데(2026-09-16 추가), 그 전에 학생이 처음부터 구체적
    # 규칙명으로 물어보게 칩으로 유도한다.
    suggested = [f"{it['name']} 왜 틀렸어?" for it in items] if len(items) > 1 else []
    return {"answer": answer, "source": [{"chunk_id": it["rule_id"]} for it in items],
            "offtopic": False, "suggested": suggested}


# ─────────────────────────────────────────────────────────────────────────────
# 검색 기반 답변 — docs/2026.09.14 검색 함수 계약 (textbook·examples·faq).md
# ask()가 _hybrid_answer()를 통해 이 경로를 부른다(계약 TTS 담당 수정 목록 1번, 2026-09-16 연결).
# search_faq/search_rule_aliases/search_textbook이 먼저 후보를 좁히고 faq_hit/rule_hit/절대점수로
# "뚜렷한 게 있는지" 판정한 뒤, 있으면 그 안에서만 LLM이 답을 짓는다 — 옛 폴백(FAQ 전체를
# 프롬프트에 통째로 넣던 방식, _answer())은 정리 완료(계약 9번, 2026-09-16). _hybrid_answer()가
# 먼저 오늘까지 쌓인 결정적 로직(_local_match 등)을 시도한 뒤에만 여기로 넘어온다.
# ─────────────────────────────────────────────────────────────────────────────

RETRIEVAL_PROMPT = """너는 초등학교 {grade}에게 영어를 가르치는 다정한 선생님이다.
아래 "검색된 자료"만 근거로 학생 질문에 답한다. 자료에 없는 내용은 답하지 않는다.

## 검색된 자료 (이 안에서만 답을 짓는다)
{candidates_block}
{log_block}
## 이 학생의 오답노트 (톤 참고용 — 답 근거로는 쓰지 않는다)
{notebook_block}

## 방금 나눈 대화
{history_block}

## 학생 질문
{question}

## 출력 JSON
{{
  "answer": "답변 2~3문장, 한국어, 초등학생이 이해할 수 있게",
  "used_id": "실제로 답에 쓴 자료의 id (예: p-0282, w-0282, R-01). 여러 개 썼으면 가장 중요한 것 하나",
  "offtopic": true 또는 false
}}"""


def _candidates_block(patterns: list[dict], words: list[dict], rule: dict | None) -> str:
    lines = [f"- [{p['id']}] (교과서 문장) {p['text']} — {p['meaning']}" for p in patterns]
    lines += [f"- [{w['id']}] (단어) {w['word']} — {w['meaning']} (예: {w['example']})" for w in words]
    if rule:
        line = f"- [{rule['id']}] (문법 규칙) {rule['type']}: {rule['text']}"
        examples = rule.get("examples") or []
        if examples:
            line += " 예: " + " / ".join(examples[:2])
        lines.append(line)
    return "\n".join(lines) if lines else "(없음)"


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


def _with_rule_examples(text: str, examples: list[str] | None) -> str:
    # 규칙 100개 중 81개가 text 안에 이미 "예: ..." 형태로 examples를 담고 있어서, 그 위에 또
    # examples를 붙이면 같은 예문이 두 번 나간다(2026-09-16, "다른 예문 보여줘" 실사용 테스트에서
    # 발견). text에 이미 있는 예문은 빼고 붙인다.
    new_examples = [ex for ex in (examples or [])[:2] if ex not in text]
    return f"{text} 예: {' / '.join(new_examples)}" if new_examples else text


def _referential_rule_answer(question: str, student: str, ctx_rule_id: str | None) -> dict | None:
    """"다른 예문 보여줘"/"다시 설명해줘"/"왜요?" 같은 이어가기(_REFERENTIAL_PATTERN)는 검색하면
    무관한 FAQ에 걸리기 쉬워서(2026-09-14 팀 실측 — "다른 예문 보여줘"가 FAQ에 잘못 매칭됨)
    검색 없이 직전 규칙 문서로 바로 답한다.

    직전 답이 규칙 하나가 아니라 여러 개를 한 번에 요약한 거면(예: _notebook_summary_answer의
    "OO를 3번, XX를 2번 틀렸어요") 첫 번째로 추측해서 답하지 않고 어느 걸 묻는지 되묻는다(옛
    _answer()의 PROMPT 6번 규칙과 같은 방식, 2026-09-16 되살림) — ctx.rule_id로 화면이 직접
    특정 규칙을 지정해준 경우는 모호하지 않으니 그대로 쓴다."""
    if not _REFERENTIAL_PATTERN.search(question):
        return None
    rule_id = ctx_rule_id
    if not rule_id:
        last = next((t for t in reversed(_recent_chat_turns(student, max_turns=5)) if t.get("rule_ids")), None)
        if last and len(last["rule_ids"]) > 1:
            names = [r["type"] for r in (golden.find_rule(rid) for rid in last["rule_ids"]) if r]
            if len(names) > 1:
                return {"answer": ", ".join(names[:-1]) + f" 얘기야, 아니면 {names[-1]} 얘기야?",
                        "source": [], "offtopic": False, "suggested": []}
        if last:
            rule_id = last["rule_ids"][0]
    if not rule_id:
        return None
    rule = golden.find_rule(rule_id)
    if not rule:
        return None
    answer = _with_rule_examples(rule["text"], rule.get("examples"))
    return {"answer": answer, "source": [{"chunk_id": rule["id"]}], "offtopic": False, "suggested": []}


_CASUAL_CHAT_PATTERN = re.compile(
    r"(날씨|기분|컨디션)\s*(가|이)?\s*(어때|어떄)|"
    r"(점심|저녁|아침|간식|급식)\s*(이|가)?\s*(뭐|뭘)|"
    r"숙제\s*있|"
    # "오늘 몇시야"류 잡담이 "여행이 몇 시인지" 같은 교과서 문장과 우연히 겹쳐서 답변까지
    # 나가버리는 문제(2026-09-16, 100문항 수동 테스트에서 발견) — 시각을 묻는 잡담도 거절 대상에 추가.
    # 영어·"영어" 언급이 있으면(예: "몇 시를 영어로 어떻게 말해요?") 위의 [A-Za-z]|영어 가드에서 이미 걸러진다.
    r"지금\s*몇\s*시|몇\s*시(야|이야|예요|이에요)"
)


def _casual_chat_reject(question: str) -> dict | None:
    """"오늘 날씨 어때?"/"점심 뭐 먹지?" 류 일상 잡담 — 교과서 단어(sunny/homework 등)와
    우연히 겹쳐서 검색이 "찾았다"고 오판하기 쉽다(2026-09-16 재현 — sharp()의 격차 조건을
    없애고 절대점수만 보게 되면서 word 0.81 같은 진짜 교과서 단어 점수가 그대로 통과해버림).
    "영어로"/영어 낱말이 있으면 진짜 학습 질문("날씨를 영어로 어떻게 말해요?")일 수 있어서
    안 걸리게 한다."""
    if re.search(r"[A-Za-z]|영어", question):
        return None
    if _CASUAL_CHAT_PATTERN.search(question):
        return {"answer": "그건 우리 교과서에서 배우는 내용이 아니에요. 선생님께 물어볼까?",
                "source": [], "offtopic": True, "suggested": []}
    return None


def _retrieval_answer(question: str, body: AskIn, skip_similar: bool = False,
                       all_faqs: list[dict] | None = None, skip_word_lookup: bool = False) -> dict:
    """계약 문서 2-1절(2026-09-14 개정): search_faq + search_textbook 이 먼저 후보를 좁힌다.
    9/15 저녁 개정판 순서: 0) 의도 가르기(인사·감정 고정답, 이어가기는 직전 규칙) 1) FAQ+faq_hit
    2) 규칙 별칭+rule_hit 3) 단어장 lookup_word(임베딩 없음) 4) search_textbook(학년별, sharp
    대신 절대점수 0.80/0.78 + 현재 유닛 자료 보강) 5) 거절. 어디에도 없으면 "우리 교과서에 없다"로
    거절(유닛 필터는 검색 자체엔 안 함 — 색인이 유닛별이 아님, 안내 문구에만 씀).

    skip_similar: _hybrid_answer()가 이미 _similar_match를 같은 인자로 확인하고 실패한 뒤에
    호출할 때 True — 똑같은 결정적 함수를 똑같은 입력으로 또 부르는 낭비를 없앤다(2026-09-16
    발견). _retrieval_answer()를 단독으로 부를 때(비교 스크립트 등)는 기본값 False로 그대로 확인.

    all_faqs: _hybrid_answer()가 이미 golden.faqs()로 읽어둔 걸 넘겨줄 때 사용 — 안 넘기면
    (단독 호출 시) 여기서 직접 읽는다. golden.faqs()는 캐싱이 없어 매번 파일을 다시 읽고
    파싱하므로, 호출부가 이미 읽어둔 걸 또 읽는 낭비를 없앤다(2026-09-16 발견).

    skip_word_lookup: _hybrid_answer()의 _local_match()가 같은 level로 textbook.lookup_word()를
    이미 시도하고 실패한 뒤에 호출할 때 True — lookup_word는 결정적이라 같은 질문·같은 level로
    또 불러봐야 같은 결과라서 낭비다(2026-09-16 발견, _similar_match와 같은 종류의 문제)."""
    ctx = body.context
    level = ctx.level or DEFAULT_LEVEL

    # 0) 의도 가르기 — 검색 전에 코드로. 인사·감사·감정은 고정 답, 이어가기는 직전 규칙 문서로.
    fixed = _intent_fixed_reply(question)
    if fixed is not None:
        return fixed
    referential = _referential_rule_answer(question, body.student, ctx.rule_id)
    if referential is not None:
        return referential
    casual = _casual_chat_reject(question)
    if casual is not None:
        return casual

    # "비슷한 거 있어?/다른 건 없어?" 류는 검색 없이 기존 로직 그대로 — 방금 답의 근거 규칙으로
    # 결정적으로 찾는 게 이미 검증돼 있고 검색보다 안전하다(2026-09-14).
    if all_faqs is None:
        all_faqs = golden.faqs()
    if not skip_similar:
        similar = _similar_match(question, body.student, all_faqs)
        if similar is not None:
            return similar

    from backend import embedding, textbook

    # 3) 단어장 조회 — 임베딩 전에, 결정적. 영어→뜻·한국어→영어 둘 다 이 하나로 (기존 _word_match
    # 는 여기서 제거 — lookup_word가 그 역할을 대신함, 2026-09-15 팀 결정).
    # skip_word_lookup=True면 1단계(_local_match)가 이미 같은 level로 시도해서 건너뜀(2026-09-16).
    if not skip_word_lookup:
        word_hits = textbook.lookup_word(question, level=level)
        if word_hits and not _PROPERTY_TAIL.search(question):
            w = word_hits[0]
            # lookup_word의 한국어 뜻 매칭은 순수 부분일치라 "형"(뜻)이 "과거형"/"형용사" 안에도
            # 걸려서 완전히 무관한 답이 나가는 문제가 있었다(2026-09-16 재현 — "과거형이 뭐예요?"가
            # brother로 답함, "오늘 날씨 어때?"/"숙제 있어?"가 today/homework 뜻풀이로 새버림).
            # 영어 낱말이 질문에 그대로 있는 정방향(예: "bus가 뭐예요?")은 안전하니 그대로 믿고,
            # 역방향(한국어→영어)은 "영어로" 같은 번역 의도 표시가 있을 때만 믿는다.
            eng_in_q = w["word"].lower() in question.lower()
            asks_translation = bool(re.search(r"영어로|영어\s*(단어|낱말)", question))
            if eng_in_q or asks_translation:
                return _word_answer(w, ctx_unit=ctx.unit, level=level)

    try:
        qvec = embedding.embed_query(question)
    except Exception as e:
        # 빈 답변("")은 학생 화면에 아무것도 안 뜨는 것처럼 보여서(2026-09-16 지적), 다른 거절
        # 문구들과 같은 톤으로 원인(서버 문제)을 알려주고 다시 시도하라고 안내한다. error 필드는
        # 그대로 남겨서 로그로는 진짜 원인을 알 수 있게 한다.
        return {"answer": "지금 검색 기능에 문제가 생겼어요. 잠시 후 다시 물어보거나 선생님께 물어볼까?",
                "source": [], "offtopic": True, "suggested": [], "error": f"임베딩 실패: {e}"}

    rule_id = ctx.rule_id
    if not rule_id:
        last = next((t for t in reversed(_recent_chat_turns(body.student, max_turns=5)) if t.get("rule_ids")), None)
        if last:
            rule_id = last["rule_ids"][0]

    # 절대 점수만 보는 검색(FAQ 0.85·규칙별칭 0.86·패턴 0.80·단어 0.78)은 전부 의미상 가까운
    # 딴 걸 오매칭하는 같은 위험이 있어서(2026-09-16 재현 — "치킨이 영어로 뭐야?"가 "cook"에,
    # "숫자 세는 법 알려줘"가 "seven"에 매칭돼 확신에 찬 오답이 나감) 질문과 후보 자신의 낱말이
    # 하나도 안 겹치면 찾은 걸로 안 친다. 아래 여러 곳(FAQ·규칙별칭·패턴·단어)이 같이 쓴다.
    qwords = _content_words(question)

    def _overlaps_question(cand_text: str) -> bool:
        cwords = _content_words(cand_text)
        for w in qwords:
            for x in cwords:
                if len(w) < 2 or len(x) < 2:
                    continue
                if w == x or (abs(len(w) - len(x)) <= 2 and (w in x or x in w)):
                    return True
                # 어미·조사만 다른 같은 어근("인사한다는" vs "인사예요")도 겹침으로 인정 — 완전
                # substring 조건만 쓰면 이런 활용형 차이를 못 잡아서 정답까지 걸러버렸다(2026-09-16,
                # "선생님을 만나면 인사한다는 문장" 회귀로 발견).
                if len(w) >= 3 and len(x) >= 3 and w[:2] == x[:2]:
                    return True
        return False

    # 1) FAQ는 질문 형식이 다 비슷해 점수 분포가 늘 촘촘해서(sharp의 격차 기준이 안 통함) 절대
    # 점수로만 판정하는 faq_hit()를 쓴다(2026-09-14, RAG 담당 실측 — sharp() 대신).
    faq_hits = textbook.search_faq(question, k=3, rule_id=rule_id, qvec=qvec)
    if textbook.faq_hit([f["score"] for f in faq_hits]):
        f = faq_hits[0]
        # faq_hit()가 통과해도 임베딩이 표면적 낱말 하나(예: "pencil")만 보고 완전히 다른 주제의
        # FAQ를 골라오는 경우가 있어서(2026-09-14 재현 — "pencil이 뭐예요?"가 "Whose는 어떻게
        # 써요?"(F-76, 예문에 pencil이 있을 뿐)에 0.86으로 매칭됨) — 질문과 FAQ가 실제 내용어를
        # 하나라도 공유하는지 확인한다. 단, 정확히 같은 문자열 비교(set 교집합)는 "many랑"/"many"처럼
        # 조사가 어순에 따라 다르게 붙는 것도 놓쳐서(같은 질문의 순서만 바뀐 변형도 무겹침 처리됨),
        # _best_match()가 이미 쓰는 부분일치(길이차 2 이내 + 서로 포함) 방식을 쓰되, 길이 기준은
        # 2로 낮춘다 — _best_match()의 3은 한국어 조사·어미 기준이라 "in"/"on"처럼 짧아도 이 도메인
        # (전치사 FAQ)에서 핵심 내용어인 영어 단어까지 걸러버림(2026-09-14, "in이랑 on 차이" 재현 —
        # faq_hit 0.876으로 정답을 찾고도 이 필터 때문에 거절됨). faq_hit()가 이미 임베딩 유사도
        # 0.85를 걸러준 뒤라 길이를 낮춰도 무관한 매칭이 새어들 위험은 낮다.
        qwords = _content_words(question)
        fwords = _content_words(f["question"] + " " + f["matched"])
        # "go랑 went 뭐가 달라요?"가 "go+동명사" FAQ(변형에 "go"가 우연히 들어있음)에 매칭되던
        # 문제(2026-09-16 재현) — 질문에 영단어가 2개 이상이면(비교 질문 가능성) 그중 하나만
        # 겹쳐선 안 되고 전부 겹쳐야 인정한다. "in이랑 on 차이"처럼 진짜 관련 FAQ는 in/on 둘 다
        # 들어있어서 여전히 통과하고("F-12" 확인됨), "go"만 우연히 겹친 무관한 FAQ는 "went"가
        # 없어서 걸러진다.
        eng_tokens = set(re.findall(r"[a-z]+", question.lower()))
        if len(eng_tokens) >= 2:
            fwords_eng = set(re.findall(r"[a-z]+", (f["question"] + " " + f["matched"]).lower()))
            overlap = eng_tokens <= fwords_eng
        elif len(qwords) >= 2:
            # 한국어만 있는 질문도 내용어가 2개 이상이면 같은 기준을 적용한다 — "저녁 인사 영어로"가
            # F-14(작별 인사, farewell)에 매칭되던 문제(2026-09-17 실사용 테스트로 발견): 진짜
            # 화제어 "저녁"은 하나도 안 겹치는데 "인사"·"영어로"처럼 이 유닛 FAQ 여러 개에 공통으로
            # 나오는 말만 겹쳐도 통과해서, 교재에 없는 화제(저녁 인사)를 전혀 다른 화제(작별 인사)
            # 답으로 자신 있게 내보냈다. 내용어 전부가 겹쳐야 인정하면 이런 "틀만 같고 화제어는
            # 다른" 오매칭을 막을 수 있다("in이랑 on 차이"류 영단어 규칙과 같은 논리).
            overlap = all(
                any(len(w) >= 2 and len(x) >= 2 and abs(len(w) - len(x)) <= 2 and (w in x or x in w) for x in fwords)
                for w in qwords
            )
        else:
            overlap = any(len(w) >= 2 and len(x) >= 2 and abs(len(w) - len(x)) <= 2 and (w in x or x in w)
                          for w in qwords for x in fwords)
        if overlap:
            source = [{"chunk_id": rid} for rid in f["rule_ids"]] + [{"chunk_id": f["id"]}]
            suggested = _followup_questions(f["rule_ids"], all_faqs, exclude_id=f["id"])
            return {"answer": f["answer"], "source": source, "offtopic": False, "suggested": suggested}
        print(f"[ask][진단] faq_hit={f['id']} 통과했는데 질문과 내용어 안 겹쳐 폐기: {f['matched']!r}", flush=True)
        # FAQ가 문턱 미달이면 그 rule_ids를 규칙 힌트로도 안 쓴다(2026-09-14 계약 8번) — 2)
        # 규칙 별칭 검색이 이 역할을 대신하므로 부정확한 소스가 될 뿐이다.

    # 2) 규칙 별칭 — "과거시제가 뭐예요?" 같은 문법 용어 질문. 한국어 질문으로 rag.search_rules를
    # 직접 돌리는 건 신뢰 못 함(9/14 실측 — "can" 질문에 R-15 will이 1위) 대신 이름·요약을 별도
    # 색인한 rule_hit(0.86)로 판정.
    rule_alias_hits = textbook.search_rule_aliases(question, k=3, qvec=qvec)
    rule = golden.find_rule(rule_alias_hits[0]["id"]) if rule_alias_hits and textbook.rule_hit([r["score"] for r in rule_alias_hits]) else None
    rule_ok = bool(rule) and _overlaps_question(f'{rule["type"]} {rule.get("short", "")} {rule["text"]}')
    if not rule_ok and rule_alias_hits and rule_alias_hits[0]["score"] >= 0.75:
        # 규칙명 자체에 오타가 있으면(예: "괴거시제" vs "과거시제") 임베딩 점수가 문턱(0.86) 밑으로
        # 떨어지거나, 위 _overlaps_question의 접두 2글자 일치 조건도 같이 못 넘어서 둘 다
        # 걸러지는 문제가 있었다(2026-09-16, 100문항 수동 테스트). 그래도 임베딩이 여전히 1위로
        # 꼽았고(0.75 이상) 편집거리(difflib)로 봐도 질문의 핵심 단어가 그 규칙 이름과 충분히
        # 가까우면(0.6 이상) 구제한다 — "미래시제"·"과거시제"처럼 진짜 다른 개념끼리는 0.44
        # 밖에 안 나와서 안 걸린다(직접 계산해 확인).
        cand = golden.find_rule(rule_alias_hits[0]["id"])
        if cand and _fuzzy_rule_name_match(question, cand):
            rule, rule_ok = cand, True
    rule_examples = rule_alias_hits[0].get("examples") if rule_ok else None

    # 4) 패턴·단어 — sharp()는 한국어 질문에서 격차가 0.01~0.04라 한 번도 안 통과해서(2026-09-14
    # 팀 실측) 절대 점수(패턴 0.80/단어 0.78)로 바꾼다. 지금 유닛의 패턴·단어(golden.patterns/words,
    # 임베딩 없이 결정적)도 최대 5개씩 더해서 후보를 넓힌다.
    tb = textbook.search_textbook(question, level=level, k_pattern=3, k_word=3, qvec=qvec)
    pattern_ok = (bool(tb["patterns"]) and tb["patterns"][0]["score"] >= 0.80
                  and _overlaps_question(f'{tb["patterns"][0]["text"]} {tb["patterns"][0]["meaning"]}'))
    word_ok = (bool(tb["words"]) and tb["words"][0]["score"] >= 0.78
               and _overlaps_question(f'{tb["words"][0]["word"]} {tb["words"][0]["meaning"]}'))

    if rule_ok or pattern_ok or word_ok:
        patterns, words = list(tb["patterns"]), list(tb["words"])
        if ctx.unit:
            seen_p, seen_w = {p["id"] for p in patterns}, {w["id"] for w in words}
            patterns += [{**p, "unit": ctx.unit} for p in golden.patterns(level, ctx.unit)[:5] if p["id"] not in seen_p]
            words += [{**w, "unit": ctx.unit} for w in golden.words(level, ctx.unit)[:5] if w["id"] not in seen_w]

        rule_for_prompt = {**rule, "examples": rule_examples} if rule else None

        log = _log_entry(ctx.log_id) if ctx.log_id else None
        log_block = ""
        if log:
            log_block = (
                "\n## 방금 학생이 만든 문장\n"
                f'원래 문장: {log.get("text", "")}\n'
                f'고친 문장: {log.get("fixed", "")}\n'
                "(둘이 같으면 원래 문장이 맞았다는 뜻)\n"
            )
        elif ctx.text:
            log_block = f"\n## 학생이 방금 입력했지만 아직 고쳐주기 전인 문장\n{ctx.text}\n"

        try:
            from backend.student import notebook_text
            notebook_block = notebook_text(body.student)
        except Exception:
            notebook_block = "(모름)"

        prompt = RETRIEVAL_PROMPT.format(
            grade=f"{level}학년", candidates_block=_candidates_block(patterns, words, rule_for_prompt),
            log_block=log_block, notebook_block=notebook_block,
            history_block=_history_block(body.student), question=question,
        )
        try:
            out = llm.generate_json(prompt)
        except llm.LLMError as e:
            return {"answer": "", "source": [], "offtopic": True, "error": str(e)}
        answer = out.get("answer") or ""
        used_id = out.get("used_id")
        fallback_id = rule["id"] if rule_ok else (tb["patterns"][0]["id"] if pattern_ok else tb["words"][0]["id"])
        suggest_rule_id = rule["id"] if rule_ok else (tb["patterns"][0].get("rule_id") if pattern_ok else None)
        suggested = _followup_questions([suggest_rule_id], all_faqs) if suggest_rule_id else []

        # LLM이 검색된 자료를 무시하고 완전히 무관한 답을 짓는 경우가 있어서(2026-09-14 재현 —
        # "pencil이 뭐예요?"가 검색은 pencil을 맞게 찾았는데 답은 소유격 얘기를 함) — 답변이 검색된
        # 후보(패턴·단어·규칙) 중 최소 하나와 실제로 내용이 겹치는지 확인한다. 안 겹치면 LLM 자유
        # 답변을 버리고 1위 후보로 결정적으로 답한다 — 검색 자체는 이미 신뢰할 만하다고 판정됐다.
        candidate_texts = [f'{p["text"]} {p["meaning"]}' for p in patterns]
        candidate_texts += [f'{w["word"]} {w["meaning"]}' for w in words]
        if rule_for_prompt:
            candidate_texts.append(f'{rule_for_prompt["type"]} {rule_for_prompt["text"]}')
        grounded = any(set(_content_words(answer)) & set(_content_words(t)) for t in candidate_texts)

        if not grounded:
            print(f"[ask][진단] 검색 후보와 답변 내용이 안 겹쳐 LLM 답 버리고 1위 후보로 답함: {answer!r}", flush=True)
            if rule_ok:
                answer = _with_rule_examples(rule["text"], rule_examples)
            elif pattern_ok:
                top = tb["patterns"][0]
                answer = f'{top["text"]} — {top["meaning"]}' if top["meaning"] else top["text"]
            else:
                top = tb["words"][0]
                answer = f'{top["word"]}는 \'{top["meaning"]}\'{_ira_neun(top["meaning"])} 뜻이에요.' + (f' 예: {top["example"]}' if top.get("example") else "")
            used_id = None

        if grounded and bool(out.get("offtopic")):
            # 후보와 답변 내용은 겹치지만(grounded) LLM 스스로 offtopic이라고 판단한 경우 —
            # 지금까지는 이 answer를 그대로 내보내서 "모른다면서 무관한 후보 내용을 억지로
            # 덧붙이는" 이상한 문장이 나갔다(2026-09-16 "저녁메뉴 뭐야?"가 아침식사 관련 패턴에
            # 0.80으로 오매칭되며 재현 — "저녁 메뉴는 모르지만 아침 식사는 중요한 끼니예요!").
            # 후보 자체가 오매칭이라 답을 억지로 짜맞출 근거가 없으니, 5)와 같은 깔끔한 거절로
            # 통일한다.
            return {"answer": "그건 우리 교과서에서 배우는 내용이 아니에요. 선생님께 물어볼까?",
                    "source": [], "offtopic": True, "suggested": []}

        # 다른 유닛 자료로 답했으면 거절 대신 어느 유닛 내용인지 앞에 붙인다(2026-09-14 계약 7번).
        # "ALL"(유닛 무관 공통 규칙 — 100개 중 10개가 이 값)은 불일치로 안 본다. 안 걸러주면
        # "ALL에서 배우는 내용이에요"라는 말이 안 되는 안내가 나간다(2026-09-16 구조 점검에서 발견,
        # rule_alias_hits가 이 규칙들도 그대로 검색 대상이라 재현 가능했음).
        final_id = used_id or fallback_id
        used_cand = next((c for c in (patterns + words) if c["id"] == final_id), None)
        cand_unit = rule.get("unit") if (rule_ok and final_id == rule["id"]) else (used_cand.get("unit") if used_cand else None)
        if cand_unit and ctx.unit and cand_unit not in (ctx.unit, "ALL"):
            answer = f"{cand_unit}에서 배우는 내용이에요. {answer}"

        return {"answer": answer, "source": [{"chunk_id": final_id}], "offtopic": False, "suggested": suggested}

    # 5) 전부 실패하기 직전 최후 수단 — 질문에 나온 영단어가 어느 규칙 본문에 실제로 같이
    # 나오면(_word_pair_rule_answer) 그걸로 답한다. FAQ·규칙별칭·패턴·단어 검색이 전부 이미
    # 실패한 뒤에만 호출해서, 더 정교한 기존 답변을 덮어쓰지 않는다.
    word_pair = _word_pair_rule_answer(question)
    if word_pair is not None:
        return word_pair

    # 5) 전부 실패 — 1위 점수가 어느 정도(0.8) 있으면 "완전 무관"은 아니라고 보고 유닛을 알려준다.
    # 진짜 엉뚱한 질문(예: "오늘 날씨 어때?")까지 아무 유닛이나 갖다 붙이지 않기 위한 최소선
    # (임시값, sharp()의 top/gap처럼 실측 조정 필요).
    top_pattern = tb["patterns"][0] if tb["patterns"] else None
    top_word = tb["words"][0] if tb["words"] else None
    best = max([x for x in (top_pattern, top_word) if x], key=lambda x: x["score"], default=None)
    # 거절 문구는 "이 유닛"이 아니라 "우리 교과서" 전체 기준(2026-09-14 계약 문서 개정 — 색인이
    # 유닛별이 아니라 전체이므로, 지금 화면의 유닛 밖이라고 거절할 근거가 없다. 정말 교과서
    # 어디에도 없을 때만 거절).
    unit_hint = best["unit"] if best and best["score"] >= 0.8 else None
    reject = (f"그건 지금 배우는 내용이 아니라 {unit_hint}에서 배워요. 선생님께 물어볼까?" if unit_hint
              else "그건 우리 교과서에서 배우는 내용이 아니에요. 선생님께 물어볼까?")
    return {"answer": reject, "source": [], "offtopic": True, "suggested": []}


def _hybrid_answer(body: AskIn) -> dict:
    """ask()가 실제로 부르는 함수(계약 문서 TTS 담당 수정 목록 1번, 2026-09-16 연결). 결정적
    예외처리(오답노트 규칙 라우팅·빈 노트 가드·a/an·비슷한 거 더·로컬 FAQ/규칙/패턴/단어 매칭)를
    먼저 시도하고, 전부 실패했을 때만 검색 기반 _retrieval_answer()로 넘긴다 — 옛 _answer()가
    쓰던 "FAQ 전체를 프롬프트에 통째로 넣고 LLM이 고르게 함" 폴백은 검색 기반으로 완전히
    대체돼서 삭제됐다(계약 9번, 2026-09-16)."""
    question = _normalize_filler_typos(body.question.strip())
    if not question:
        return {"answer": "", "source": [], "offtopic": True}

    if (_CORRECTNESS_PATTERN.search(question) and re.search(r"[A-Za-z]", question)
            and not re.search(r"왜|어떻게", question)):
        if not settings.has_api_key:
            return {"answer": "", "source": [], "offtopic": True, "error": "GEMINI_API_KEY 미설정"}
        try:
            return _check_correctness(question, level=body.context.level or DEFAULT_LEVEL)
        except llm.LLMError:
            return _CORRECTNESS_FALLBACK

    if (_CORRECTNESS_PATTERN.search(question) and not re.search(r"[A-Za-z]", question)
            and body.context.text and not re.search(r"왜|어떻게", question)):
        if not settings.has_api_key:
            return {"answer": "", "source": [], "offtopic": True, "error": "GEMINI_API_KEY 미설정"}
        try:
            return _check_correctness(body.context.text, level=body.context.level or DEFAULT_LEVEL)
        except llm.LLMError:
            return _CORRECTNESS_FALLBACK

    all_faqs = golden.faqs()
    all_rules = golden.rules()
    if not all_faqs and not all_rules:
        return {"answer": "", "source": [], "offtopic": True, "error": "faq.jsonl/rules.jsonl 이 없음"}

    notebook_rule = _notebook_rule_answer(question, body.student)
    if notebook_rule is not None:
        return notebook_rule

    if _NOTEBOOK_TRIGGER.search(question) and _notebook_content_word_count(question) <= 3:
        from backend.student import notebook_text
        if notebook_text(body.student) == "아직 오답노트가 비어 있음.":
            return {"answer": "아직 오답노트에 기록된 게 없어요! 문제를 몇 개 풀어보면 그때 자주 틀리는 것도 알려줄 수 있어요.",
                    "source": [], "offtopic": False, "suggested": []}
        # "이거 왜 틀렸어?"처럼 이어가기 표현("틀렸다") 자체가 _NOTEBOOK_TRIGGER에도 걸려서, 방금
        # 요약 답변 뒤에 되묻기(_referential_rule_answer)로 가야 할 질문이 여기서 또 가로채 같은
        # 요약을 반복하는 문제가 있었다(2026-09-16 발견) — 이어가기면 여기서 건너뛰고 아래에서
        # _referential_rule_answer가 처리하게 둔다.
        if not _REFERENTIAL_PATTERN.search(question):
            notebook_summary_ans = _notebook_summary_answer(question, body.student)
            if notebook_summary_ans is not None:
                return notebook_summary_ans

    a_an = _a_an_answer(question) or _a_an_followup_answer(question, body.student)
    if a_an is not None:
        return a_an

    similar = _similar_match(question, body.student, all_faqs)
    if similar is not None:
        return similar

    words_pool = {w["word"].lower(): w for w in golden.all_words()}
    patterns_pool = golden.all_patterns()
    level = body.context.level or DEFAULT_LEVEL
    # _local_match의 단어장 조회(lookup_word)는 영단어가 2개 이하일 때만 도는데, 그게 돌고도
    # 실패했다면 _retrieval_answer()가 같은 level로 또 불러봐야 결과가 같으므로(결정적 함수)
    # 건너뛴다 — 2개 넘게 섞인 질문은 _local_match가 애초에 안 돌렸으니 거기서 처음이자
    # 유일하게 시도해야 한다(2026-09-16 발견).
    referential = _REFERENTIAL_PATTERN.search(question)
    en_word_count = len(re.findall(r"[A-Za-z']+", question))
    # "water 이거 머임?"처럼 질문 자체에 조회할 영단어가 이미 있으면 "이거"는 직전 대화가 아니라
    # 그 단어를 가리키는 것으로 본다 — "이거"가 있다는 이유만으로 무조건 이어가기 취급해서
    # 문장 안에 이미 있는 답을 로컬 매칭도 안 해보고 놓치던 문제(2026-09-16, 오프토픽/필러
    # 경계 테스트에서 발견). 영단어가 하나도 없을 때만(순수 지시어, "이거 왜 틀렸어?" 등)
    # 이어가기로 보고 로컬 매칭을 건너뛴다.
    treat_as_referential = bool(referential) and en_word_count == 0
    # "buy랑 bought랑 뭔 차이야?"/"go랑 went 뭐가 달라?"류 비교 질문은 영단어가 정확히 2개라
    # 아래 "영단어 ≤2개면 단어장 조회" 지름길에 걸려서, X 하나만 붙잡고 단어 뜻풀이로 잘못
    # 답했다(2026-09-17 실사용 테스트 발견 — "buy랑 bought"가 "buy는 사다예요"로 답변됨, 정작
    # 정답 FAQ(F-125 "buy 과거형이 뭐예요", 0.863)는 검색 경로에만 있어서 이 지름길이 먼저
    # 가로채면 도달 못 함). 비교 질문이면 단어장 조회를 아예 건너뛰고 검색 경로로 보낸다.
    is_comparison = bool(_COMPARE_PATTERN.search(question))
    word_lookup_attempted = not treat_as_referential and (is_comparison or en_word_count <= 2)
    if not treat_as_referential:
        local = _local_match(question, all_faqs, all_rules, words_pool, patterns_pool, level=level,
                              ctx_unit=body.context.unit, skip_word_lookup=is_comparison)
        if local is not None:
            return local

    # 여기까지 전부 실패해야만 검색 기반 경로로 — 바로 위에서 _similar_match를 이미 확인했고
    # (skip_similar=True), all_faqs도 이미 읽어뒀고(golden.faqs() 재호출 방지), 위 word_lookup_
    # attempted면 lookup_word도 이미 시도했거나(skip_word_lookup) 비교 질문이라 아예 부적절하니
    # 전부 중복 호출을 없앤다(2026-09-16, is_comparison 조건은 2026-09-17 추가).
    return _retrieval_answer(question, body, skip_similar=True, all_faqs=all_faqs,
                              skip_word_lookup=word_lookup_attempted)
