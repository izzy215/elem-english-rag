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
      - error: 위 필드 대신(정상 시엔 없음) API 키 미설정·STT 실패 등의 사유 문자열이 담길 수 있습니다
        → 화면에서는 error 유무만 보고 "채점 실패/다시 시도" 처리하면 되비다
"""
import base64
import difflib
import re

from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend import golden
from backend.config import settings

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

    if not settings.has_api_key:
        return {"heard": "", "expected": expected, "score": 0, "passed": False, "error": "GEMINI_API_KEY 미설정"}

    try:
        heard = gemini_stt(body.audio_base64, body.mime)
    except Exception as e:
        return {"heard": "", "expected": expected, "score": 0, "passed": False, "error": str(e)}

    score = similarity(heard, expected)
    return {"heard": heard, "expected": expected, "score": score, "passed": score >= PASS_SCORE}
