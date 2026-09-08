"""
E. 말하기 평가 (PRD 5.2)   담당: TTS 팀원

POST /api/speak
body: {"student", "item_id", "audio_base64", "mime"="audio/webm", "language"=None}
  - item_id 없으면(챗봇 마이크 등) expected/score 무시하고 heard만 쓰면 됨
  - language 생략 시 오디오만 듣고 서버가 자동 판단(_detect_language)

→ 200 (항상, 예외 안 던짐):
  {"heard", "expected", "score": 0~100, "passed": score>=70,
   "pronunciation_level": "상"/"중"/"하"(passed일 때만), "error": 실패 사유}

STT_BACKEND=gemini(기본) / whisper(할당량 없이 로컬 테스트용).

language="ko"는 hybrid_stt() 사용 — Gemini 한 번으론 섞인 영어 단어(went 등)가 한국어로
뭉개져서, 로컬 Whisper 2회(한국어/영어 강제, 할당량 안 씀) + Gemini 병합 1회로 처리한다.
단어 목록·맥락 힌트는 _recent_context()/_notebook_units() 로 학생 맥락에 맞게 좁힌다.
"""
import base64
import difflib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend import golden
from backend.config import settings
from backend.pronounce import _decode_to_wav_array, pronunciation_level, pronunciation_score
from backend.tts import ensure_tts

STT_BACKEND = os.environ.get("STT_BACKEND", "gemini")
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


def whisper_stt(audio_base64: str, mime: str, language: str = "en") -> str:
    """로컬 Whisper STT (STT_BACKEND=whisper 테스트용, 할당량 안 씀). language=None이면 자동 감지."""
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    audio, _ = _decode_to_wav_array(audio_bytes, ext)
    result = _get_whisper_model().transcribe(audio, language=language, fp16=False)
    return result["text"].strip()


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
    """rag.py 완성 전 자리 표시(tutor.py 의 _search_rule() 과 같은 패턴) — 항상 None.
    완성되면:
        from backend.rag import search_rules
        hits = search_rules(text, k=1)
        return hits[0] if hits else None
    """
    return None


def hybrid_stt(audio_base64: str, mime: str, student: str = "") -> str:
    """language="ko" 인식. Whisper 로컬 2회(한국어/영어 강제, 할당량 안 씀) + Gemini 병합 1회로
    섞인 영어 단어를 보존한다. 단어 목록은 _recent_context()/_notebook_units() 로 학생 맥락에 맞게
    좁히고, 규칙 힌트는 _rag_rule_hint() → 최근 /fix → 유닛 제목 순으로 대체한다.
    병합 실패 시 한국어 강제 인식 결과를 그대로 반환한다."""
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    audio, _ = _decode_to_wav_array(audio_bytes, ext)

    model = _get_whisper_model()
    korean_guess = model.transcribe(audio, language="ko", fp16=False, temperature=0.0)["text"].strip()
    english_guess = model.transcribe(audio, language="en", fp16=False, temperature=0.0)["text"].strip()
    unit, rule_id, level = _recent_context(student)
    unit_scope = list({unit, *_notebook_units(student)} - {None}) if unit else _notebook_units(student)

    vocab = ", ".join(golden.known_english_vocab(unit_scope or None))
    rag_hit = _rag_rule_hint(korean_guess)  # rag.py 완성 전까지는 항상 None
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
    prompt = f"""아래는 초등학생이 영어 수업 챗봇에게 "질문이나 요청"을 하나 말한 음성을, 로컬
STT(Whisper)로 두 번 받아쓴 결과다(이 마이크는 챗봇한테 뭔가를 묻거나 부탁하는 용도로만 쓴다 —
"왜 ~예요?"처럼 물음표로 끝나는 질문일 수도 있고, "~보여줘"/"~만들어줘"/"~알려줘"처럼 부탁하는
문장일 수도 있다. 어느 쪽이든 항상 챗봇을 향한 말이라, 서로 무관한 평서문(예: "고양이는 동물이다"
같은 일반 사실 설명)은 나올 수 없다).
- (A) 한국어라고 가정하고 받아쓴 결과: "{korean_guess}"
- (B) 영어라고 가정하고 받아쓴 결과: "{english_guess}"

이 학생은 한국어 질문/요청 안에 아래 영어 수업 단어 목록 중 하나 이상을 섞어서 말하고 있다: {vocab}
{topic_line}
A는 한국어 조사/어미(예: 은, 는, 예요, 이에요)는 맞을 가능성이 높지만 그 안의 영어 단어를 한국어 발음으로 잘못 옮겼을 수 있고,
B는 영어 단어 자체는 맞게 알아들었을 가능성이 높지만 나머지 한국어 부분은 엉뚱한 영어로 잘못 들었을 수 있다.
두 결과와 단어 목록(+방금 다루던 규칙이 있다면 그 맥락)을 참고해서, 실제로 학생이 챗봇에게 물어보거나
부탁했을 것 같은 한국어+영어 혼용 문장 하나만 출력해라. 목록에 있는 단어를 쓸 땐 목록에 적힌 형태
그대로 써라(예: eats 를 eat 로 바꾸지 말 것).
중요: A와 B가 서로 너무 달라서 공통된 문장을 짐작하기 어려우면, 억지로 새 문장을 지어내지 말고
A를 그대로 출력해라. 학생 문장은 기본적으로 한국어 질문/요청이니, 결과가 영어 평서문 전체로
바뀌거나 챗봇과 무관한 일반 사실 설명이 되면 안 된다.
다른 설명 없이 문장만 출력."""

    try:
        resp = _get_client().models.generate_content(model=settings.gemini_model, contents=prompt)
        merged = (resp.text or "").strip().strip("\"'“”‘’")
        return merged or korean_guess
    except Exception:
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
                heard = gemini_stt(body.audio_base64, body.mime, language)
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
