"""
E. 말하기 평가 (PRD 5.2)   담당: TTS 팀원

사용법:

    POST /api/speak
    body: {"student": "A", "item_id": "s-0012", "audio_base64": "...", "mime": "audio/webm"}
      - student: 학생 id
      - item_id: words.csv/sentences.csv 의 id — 이걸로 정답 원문을 서버가 알아서 찾음
      - audio_base64: 녹음한 오디오를 base64 로 인코딩한 문자열 (브라우저 MediaRecorder 결과 등)
      - mime: 오디오 포맷. 생략하면 "audio/webm"

    → 200 (실패해도 항상 200, 예외를 던지지 않스비다):
      {"heard": "the rabbit can jump", "expected": "The rabbit can jump.", "score": 82, "passed": true}
      - heard: STT로 알아들은 내용 (안 들렸으면 "")
      - expected: item_id 의 정답 원문
      - score: 0~100 유사도
      - passed: score ≥ 70 이면 true(대충 70%면 성공했다는겁니다)
      - pronunciation_level: "상"/"중"/"하" — 선생님(TTS) 발음과의 유사도, **passed가 true일 때만** 계산됨.
        passed 판정 자체엔 영향 없음. 숫자로는 신뢰도가 낮아서(미세한 차이는 못 잡음, pronounce.py 참고)
        3단계로만 표현함. passed가 false 이거나 계산 실패 시 필드 자체가 없을 수 있음
      - error: 위 필드 대신(정상 시엔 없음) API 키 미설정·STT 실패 등의 사유 문자열이 담길 수 있습니다
        → 화면에서는 error 유무만 보고 "채점 실패/다시 시도" 처리하면 되비다

STT_BACKEND 환경변수: 기본값 "gemini"(서비스용, PRD 5.2). 테스트/튜닝 중 API 할당량 때문에
막히면 "whisper"로 바꿔서 로컬 STT(openai-whisper)로 임시 전환할 수 있다 — 요청/응답 형식은 그대로.
"""
import base64
import difflib
import os
import re

from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend import golden
from backend.config import settings
from backend.pronounce import _decode_to_wav_array, pronunciation_level, pronunciation_score
from backend.tts import ensure_tts

STT_BACKEND = os.environ.get("STT_BACKEND", "gemini")

router = APIRouter(tags=["speak"])
#통과 기준 주어진 단어나 문장 대비 70% 이상 유사하면 통과로 간주합니다
PASS_SCORE = 70


class SpeakIn(BaseModel):
    student: str
    item_id: str
    audio_base64: str
    mime: str = "audio/webm"


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def gemini_stt(audio_base64: str, mime: str) -> str:
    audio_bytes = base64.b64decode(audio_base64)
    response = _get_client().models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
            "Transcribe exactly what is spoken in English. "
            "Output only the transcript, no punctuation, no extra text.",
        ],
    )
    return (response.text or "").strip()


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def whisper_stt(audio_base64: str, mime: str) -> str:
    """STT_BACKEND=whisper 일 때만 쓰는 로컬 STT. API 할당량 없이 테스트/튜닝하려는 용도."""
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    audio, _ = _decode_to_wav_array(audio_bytes, ext)
    result = _get_whisper_model().transcribe(audio, language="en", fp16=False)
    return result["text"].strip()


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
            heard = whisper_stt(body.audio_base64, body.mime)
        else:
            heard = gemini_stt(body.audio_base64, body.mime)
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
