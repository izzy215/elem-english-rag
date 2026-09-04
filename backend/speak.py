"""
E. 말하기 평가 (PRD 5.2)   담당: TTS 팀원

POST /api/speak {student, item_id, audio_base64, mime}
→ {heard, expected, score(0~100), passed}
흐름: 오디오 → Gemini 멀티모달로 텍스트(STT) → 정규화 후 원문과 단어 단위 유사도.
음소 단위 발음 평가는 하지 않는다. passed 기준 70 (미정, PRD 11절).
"""
from fastapi import APIRouter
from pydantic import BaseModel

from backend import golden

router = APIRouter(tags=["speak"])
PASS_SCORE = 70


class SpeakIn(BaseModel):
    student: str
    item_id: str
    audio_base64: str
    mime: str = "audio/webm"


@router.post("/speak")
def speak(body: SpeakIn):
    item = golden.find_item(body.item_id)
    expected = item["text"] if item else ""
    # TODO: heard = gemini_stt(body.audio_base64, body.mime); score = similarity(heard, expected)
    return {"heard": "", "expected": expected, "score": 0, "passed": False, "todo": "STT 미구현"}
