"""
E. 말하기 평가 (PRD 5.2)   담당: TTS 팀원

POST /api/speak
body: {"student", "item_id", "audio_base64", "mime"="audio/webm", "language"=None}
  - item_id 없으면(챗봇 마이크 등) expected/score 무시하고 heard만 쓰면 됨
  - language 생략 시 오디오만 듣고 서버가 자동 판단(_detect_language)

→ 200 (항상, 예외 안 던짐):
  {"heard", "expected", "score": 0~100, "passed": score>=70,
   "pronunciation_level": "상"/"중"/"하"(passed일 때만), "error": 실패 사유}

STT_BACKEND=gemini(기본, 오디오 인식 자체는 아래처럼 전부 로컬 Whisper) / whisper(자동 감지 없이 그대로).

language="en"이면 whisper_stt() — 로컬 Whisper로 바로 받아쓴다(할당량 안 씀). 섀도잉·"내 문장 말하기"가 여기로 옴.

language="ko"는 hybrid_stt() — Whisper 2회(한국어/영어 강제) + 병합 1회(backend/llm.py 경유,
.env의 LLM_BACKEND에 따라 Gemini 또는 로컬 모델)로 섞인 영어 단어를 보존한다.
단어 목록·맥락 힌트는 _recent_context()/_notebook_units() 로 학생 맥락에 맞게 좁힌다.
"""
import base64
import difflib
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend import golden, llm
from backend.config import settings
from backend.pronounce import _decode_to_wav_array, pronunciation_level, pronunciation_score
from backend.tts import ensure_tts

STT_BACKEND = os.environ.get("STT_BACKEND", "gemini")
WHISPER_SERVER_URL = os.environ.get("WHISPER_SERVER_URL", "").strip()   # 있으면 GPU 서버(whisper_server.py)로, 없으면 로컬
SENTENCE_LOG = Path(__file__).resolve().parent.parent / "data" / "student" / "sentence_log.jsonl"

router = APIRouter(tags=["speak"])
#통과 기준 주어진 단어나 문장 대비 70% 이상 유사하면 통과로 간주합니다
PASS_SCORE = 70


class SpeakIn(BaseModel):
    student: str
    item_id: str
    audio_base64: str
    mime: str = "audio/webm"
    language: str | None = None  # None = 프론트가 안 보냄 → 서버가 오디오 듣고 자동 판단(_detect_language)


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


GEMINI_STT_LANG_NAMES = {"en": "English", "ko": "Korean"}


def gemini_stt(audio_base64: str, mime: str, language: str = "en") -> str:
    """language: "en"/"ko" 등 언어 코드. 목록에 없는 코드는 그 코드 자체를 언어 이름으로 넣는다
    (Gemini가 코드만 봐도 대체로 알아들음)."""
    audio_bytes = base64.b64decode(audio_base64)
    lang_name = GEMINI_STT_LANG_NAMES.get(language, language)
    response = _get_client().models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
            f"Transcribe exactly what is spoken in {lang_name}. "
            "Output only the transcript, no punctuation, no extra text.",
        ],
    )
    return (response.text or "").strip()


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        size = os.environ.get("WHISPER_MODEL", "base")
        _whisper_model = whisper.load_model(size, download_root=os.environ.get("WHISPER_CACHE_DIR") or None)
    return _whisper_model


def _detect_language(audio_base64: str, mime: str) -> str:
    """오디오만 듣고 언어를 자동 판단한다(Whisper 내장, 로컬·무료)."""
    import whisper
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    audio, _ = _decode_to_wav_array(audio_bytes, ext)
    model = _get_whisper_model()
    mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(audio.astype("float32"))).to(model.device)
    _, probs = model.detect_language(mel)
    return max(probs, key=probs.get)


def _remote_whisper(audio_base64: str, mime: str, language: str | None, model: str = "large-v3") -> tuple[str, float]:
    """GPU 서버의 whisper_server.py 호출. (텍스트, avg_logprob) 반환. 실패하면 예외 그대로 던짐(호출부가 로컬로 대체)."""
    body = json.dumps({"audio_base64": audio_base64, "mime": mime, "language": language, "model": model}).encode()
    req = urllib.request.Request(WHISPER_SERVER_URL.rstrip("/") + "/transcribe", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["text"], data.get("avg_logprob", -999.0)


def _transcribe(audio_base64: str, mime: str, language: str | None) -> tuple[str, float]:
    """WHISPER_SERVER_URL 설정돼 있으면 GPU 서버로, 실패하거나 설정 없으면 로컬 Whisper로. (텍스트, avg_logprob) 반환."""
    if WHISPER_SERVER_URL:
        try:
            return _remote_whisper(audio_base64, mime, language)
        except Exception as e:
            print(f"[speak] whisper 서버 호출 실패({e}) → 로컬로 대체", flush=True)
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    audio, _ = _decode_to_wav_array(audio_bytes, ext)
    result = _get_whisper_model().transcribe(audio, language=language, fp16=False, temperature=0.0)
    return result["text"].strip(), _avg_logprob(result)


def whisper_stt(audio_base64: str, mime: str, language: str = "en") -> str:
    """Whisper STT (STT_BACKEND=whisper 테스트용, 할당량 안 씀). WHISPER_SERVER_URL 있으면 GPU 서버 사용."""
    return _transcribe(audio_base64, mime, language)[0]


RECENT_RULE_WINDOW_SEC = 120  # 이 안이면 "더 물어보기"(방금 그 규칙 얘기), 넘으면 유닛 챗봇(뭐든 물어볼 수 있음)으로 봄


def _recent_context(student: str) -> tuple[str | None, str | None, int | None]:
    """sentence_log.jsonl(tutor.py 기록, 읽기 전용)에서 이 학생의 최근 (유닛, 규칙id, 레벨)을 추정.
    rule_id는 RECENT_RULE_WINDOW_SEC 이내일 때만 씀("더 물어보기") — 지나면 None(유닛 챗봇으로 간주).
    기록 없으면 (None, None, None)."""
    if not SENTENCE_LOG.exists():
        return None, None, None
    try:
        lines = SENTENCE_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None, None, None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("student") == student:
            unit = row.get("unit") or None
            level = row.get("level") if isinstance(row.get("level"), int) else None
            rule_id = row.get("rule_id") or None
            if rule_id:
                try:
                    age = (datetime.now() - datetime.fromisoformat(row.get("ts", ""))).total_seconds()
                except (TypeError, ValueError):
                    age = None
                if age is None or age > RECENT_RULE_WINDOW_SEC:
                    rule_id = None
            return unit, rule_id, level
    return None, None, None


def _notebook_units(student: str) -> list[str]:
    """오답노트에 쌓인 규칙들의 유닛 목록(student.py 의 공식 함수 사용). 오답노트 화면 챗봇은
    최근 유닛 하나가 아니라 지금까지 틀린 여러 유닛을 넘나들며 물어볼 수 있어서 범위를 넓혀 준다."""
    try:
        from backend.student import notebook_summary
        summary = notebook_summary(student)
    except Exception:
        return []
    rule_ids = [item["rule_id"] for item in summary["active"] + summary["overcome"]]
    units = {golden.find_rule(rid)["unit"] for rid in rule_ids if golden.find_rule(rid)}
    return sorted(units)


def _rag_rule_hint(text: str) -> dict | None:
    """텍스트와 가장 가까운 규칙 1개(RAG 검색, rag.py). 색인 없음·검색 실패면 None(다음 우선순위로 대체)."""
    try:
        from backend.rag import search_rules
        hits = search_rules(text, k=1)
        return hits[0] if hits else None
    except Exception as e:                                    # 색인 없음(IndexUnavailableError) 포함, 힌트 실패로 요청 자체를 막지 않음
        print(f"[hybrid_stt] rag 힌트 검색 실패 → 생략: {type(e).__name__}: {e}", flush=True)
        return None


_ENGLISH_STOPWORDS = {
    "a", "an", "the", "i", "you", "he", "she", "we", "they", "it", "is", "are", "was", "were",
    "am", "be", "been", "being", "do", "does", "did", "have", "has", "had", "to", "of", "in",
    "on", "at", "for", "with", "from", "as", "and", "but", "or", "if", "this", "that", "these",
    "those", "will", "would", "can", "could", "my", "your", "his", "her", "our", "their",
    "write", "go", "goes", "want", "know", "let", "me", "not", "no", "so", "one",
}


def _vocab_words_in(text: str, vocab_set: set[str]) -> set[str]:
    """text 안에서 vocab_set(소문자)에 있는 "의미 있는" 영단어만 뽑는다 — 관사·be동사·전치사 같은
    문법 단어는 목록에 있어도 힌트로 안 씀(2026-09-10, "have"/"to"/"write" 가 힌트를 흐리는 걸 확인)."""
    return {w for w in re.findall(r"[A-Za-z']+", text.lower()) if w in vocab_set and w not in _ENGLISH_STOPWORDS}


def _avg_logprob(result: dict) -> float:
    """model.transcribe() 결과의 세그먼트별 평균 로그확률(Whisper 자체 신뢰도)을 평균낸다.
    0에 가까울수록(덜 음수) 자신 있게 들었다는 뜻. 세그먼트가 없으면(무음 등) 아주 낮은 값."""
    segs = result.get("segments") or []
    return sum(s.get("avg_logprob", -999.0) for s in segs) / len(segs) if segs else -999.0


def _extract_sentence(text: str) -> str:
    """병합 모델이 지시를 어기고 JSON 이나 코드펜스로 감싸 와도(로컬 모델에서 관찰됨) 문장만 뽑아낸다.
    {"sentence": "..."} 모양이면 그 값을, 아니면 코드펜스/앞뒤 따옴표만 벗겨서 그대로 돌려준다."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                value = next((v for v in data.values() if isinstance(v, str) and v.strip()), None)
                if value:
                    return value.strip().strip("\"'“”‘’")
        except json.JSONDecodeError:
            pass
    return text.strip("\"'“”‘’")


def hybrid_stt(audio_base64: str, mime: str, student: str = "") -> str:
    """language="ko" 인식. Whisper 로컬 2회(한국어/영어 강제, 할당량 안 씀) + Gemini 병합 1회로
    섞인 영어 단어를 보존한다. 단어 목록은 _recent_context()/_notebook_units() 로 학생 맥락에 맞게
    좁히고, 규칙 힌트는 _rag_rule_hint() → 최근 /fix → 유닛 제목 순으로 대체한다.
    병합 실패 시 한국어 강제 인식 결과를 그대로 반환한다."""
    unit, rule_id, level = _recent_context(student)
    unit_scope = list({unit, *_notebook_units(student)} - {None}) if unit else _notebook_units(student)
    vocab_list = golden.known_english_vocab(unit_scope or None)
    vocab = ", ".join(vocab_list)
    vocab_set = {v.lower() for v in vocab_list}

    # initial_prompt 로 vocab 힌트를 줘봤으나 오탐·반복 루프가 더 늘어 실측상 안 씀(2026-09-09)
    korean_guess, ko_conf = _transcribe(audio_base64, mime, "ko")
    english_guess, en_conf = _transcribe(audio_base64, mime, "en")
    print(f"[hybrid_stt] ko 강제={korean_guess!r}(conf={ko_conf:.2f}) en 강제={english_guess!r}(conf={en_conf:.2f})", flush=True)
    if _normalize(korean_guess) == _normalize(english_guess) and korean_guess:
        # 둘이 이미 같은 문장(대개 순수 영어) → 병합 모델이 "번역"해버리는 걸 막기 위해 병합 자체를 생략
        print(f"[hybrid_stt] ko=en 이라 병합 생략, 그대로 사용", flush=True)
        return korean_guess
    if english_guess and not re.search(r"[가-힣]", english_guess) and en_conf - ko_conf > 0.3:
        # 한글 없는 온전한 영어 + 신뢰도도 더 높으면 순수 영어로 보고 그대로 사용(신뢰도까지 봐야
        # 한국어를 영어로 지어낸 오역과 구분됨)
        print(f"[hybrid_stt] en 강제가 한글 없고 신뢰도도 더 높아 그대로 사용", flush=True)
        return english_guess
    print(f"[hybrid_stt] unit={unit} rule_id={rule_id} vocab={vocab!r}", flush=True)
    rag_hit = _rag_rule_hint(korean_guess)
    print(f"[hybrid_stt] rag_hit={rag_hit['id'] if rag_hit else None}", flush=True)
    rule = golden.find_rule(rule_id) if rule_id else None
    unit_info = golden.find_unit(level, unit) if (unit and level) else None
    if rag_hit:
        topic_line = f'이 질문은 "{rag_hit["type"]}" 규칙과 관련 있어 보인다({rag_hit["text"]}).\n'
    elif rule:
        topic_line = f'방금 이 학생은 "{rule["type"]}"({rule["short"]}) 규칙을 다루고 있었다.\n'
    elif unit_info:
        topic_line = f'이 학생은 지금 "{unit_info["title"]}" 유닛 내용에 대해 물어보는 중이다.\n'
    else:
        topic_line = ""
    # en 강제 인식에만 걸린 학습 단어(ko 강제가 다른 소리로 잘못 들었을 가능성) — 신뢰도로는 못
    # 걸러내서(en 신뢰도가 항상 더 낮게 나옴, 2026-09-10 실측: cat/friend 등) 단어 등장 여부로 직접 힌트
    en_only_words = _vocab_words_in(english_guess, vocab_set) - _vocab_words_in(korean_guess, vocab_set)
    word_hint = ""
    if en_only_words:
        word_hint = f'주의: (B)에는 있는데 (A)에는 없는 학습 단어가 있다: {", ".join(sorted(en_only_words))} — (A)가 이 단어를 다른 소리로 잘못 들었을 가능성이 높으니 이 단어를 살려서 합쳐라.\n'
        print(f"[hybrid_stt] word_hint={en_only_words}", flush=True)
    prompt = f"""아래는 초등학생이 영어 수업 챗봇에게 "질문이나 요청"을 하나 말한 음성을, 로컬
STT(Whisper)로 두 번 받아쓴 결과다(이 마이크는 챗봇한테 뭔가를 묻거나 부탁하는 용도로만 쓴다 —
"왜 ~예요?"처럼 물음표로 끝나는 질문일 수도 있고, "~보여줘"/"~만들어줘"/"~알려줘"처럼 부탁하는
문장일 수도 있다. 어느 쪽이든 항상 챗봇을 향한 말이라, 서로 무관한 평서문(예: "고양이는 동물이다"
같은 일반 사실 설명)은 나올 수 없다).
- (A) 한국어라고 가정하고 받아쓴 결과: "{korean_guess}"
- (B) 영어라고 가정하고 받아쓴 결과: "{english_guess}"

이 학생은 한국어 질문/요청 안에 아래 영어 수업 단어 목록 중 하나 이상을 섞어서 말하고 있다: {vocab}
{topic_line}{word_hint}
A는 한국어 조사/어미(예: 은, 는, 예요, 이에요)는 맞을 가능성이 높지만 그 안의 영어 단어를 한국어 발음으로 잘못 옮겼을 수 있고,
B는 영어 단어 자체는 맞게 알아들었을 가능성이 높지만 나머지 한국어 부분은 엉뚱한 영어로 잘못 들었을 수 있다.
두 결과와 단어 목록(+방금 다루던 규칙이 있다면 그 맥락)을 참고해서, 실제로 학생이 챗봇에게 물어보거나
부탁했을 것 같은 한국어+영어 혼용 문장 하나만 출력해라. 목록에 있는 단어를 쓸 땐 목록에 적힌 형태
그대로 써라(예: eats 를 eat 로 바꾸지 말 것).
중요: A와 B가 서로 너무 달라서 공통된 문장을 짐작하기 어려우면(단, 위 "주의" 힌트에 나온 단어는
예외 — 그 단어만은 살려서 A에 반영해라), 억지로 새 문장을 지어내지 말고 A를 그대로 출력해라.
학생 문장은 기본적으로 한국어 질문/요청이니, 결과가 영어 평서문 전체로
바뀌거나 챗봇과 무관한 일반 사실 설명이 되면 안 된다.
출력 형식: 문장 하나만, 있는 그대로의 순수 텍스트로 출력해라. JSON·중괄호·따옴표로 감싸기·코드펜스는
절대 쓰지 말 것. 그리고 이건 번역이 아니다 — A/B에 나온 단어를 그대로 골라 이어붙이기만 하고,
전체 뜻을 다른 말로 새로 옮기지 마라(예: "I play friend" 가 섞여 있으면 "플레이"·"프렌드"처럼 그
발음/철자를 살리고, "친구랑 놀아요"처럼 뜻만 번역한 새 문장을 만들지 말 것).
다른 설명 없이 문장만 출력."""

    try:
        # 병합은 자유 재구성 작업이라 14b(서비스 기본)보다 32b가 더 안정적이었음(실측) — 이 호출만 지정
        merged = _extract_sentence(llm.generate_text(prompt, backend="merge32b"))
        print(f"[hybrid_stt] 병합 결과={merged!r}", flush=True)
        return merged or korean_guess
    except llm.LLMError as e:
        print(f"[hybrid_stt] 병합 실패({e}) → ko 강제 결과 그대로 사용", flush=True)
        return korean_guess


def _normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", text.lower()).split()


def similarity(heard: str, expected: str) -> int:
    a, b = _normalize(heard), _normalize(expected)
    if not a or not b:
        return 0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return round(ratio * 100)


@router.post("/speak")
def speak(body: SpeakIn):
    item = golden.find_item(body.item_id)
    expected = item["text"] if item else ""

    if STT_BACKEND != "whisper" and not settings.has_api_key:
        return {"heard": "", "expected": expected, "score": 0, "passed": False, "error": "GEMINI_API_KEY 미설정"}

    try:
        if STT_BACKEND == "whisper":
            heard = whisper_stt(body.audio_base64, body.mime, body.language)
        else:
            # 프론트가 language 를 안 보내면(아직 common.js 가 안 바뀐 화면 포함) 오디오만 듣고 자동 판단
            language = body.language or _detect_language(body.audio_base64, body.mime)
            if language == "ko":
                heard = hybrid_stt(body.audio_base64, body.mime, body.student)
            else:
                heard = whisper_stt(body.audio_base64, body.mime, language)
    except Exception as e:
        return {"heard": "", "expected": expected, "score": 0, "passed": False, "error": str(e)}

    score = similarity(heard, expected)
    result = {"heard": heard, "expected": expected, "score": score, "passed": score >= PASS_SCORE}

    if result["passed"]:
        try:
            ref_path = ensure_tts(body.item_id, expected)
            raw = pronunciation_score(str(ref_path), body.audio_base64, body.mime)
            result["pronunciation_level"] = pronunciation_level(raw)
        except Exception:
            pass  # 참고용 지표라 실패해도 전체 응답은 그대로 반환

    return result
