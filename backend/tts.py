"""
D. TTS (PRD 5.2)   담당: TTS 팀원

GET /api/tts/{item_id} → audio/wav. 캐시 audio_cache/{item_id}.wav
참고 구현: sample/server.py 의 ensure_tts() (Gemini TTS + wave 저장) 를 그대로 옮기면 된다.
원문은 golden.find_item(item_id) 로 찾는다.
"""
from fastapi import APIRouter, HTTPException

from backend import golden

router = APIRouter(tags=["tts"])


@router.get("/tts/{item_id}")
def tts(item_id: str):
    item = golden.find_item(item_id)
    if not item:
        raise HTTPException(404, "단어/문장 없음")
    # TODO: ensure_tts(item["text"]) → FileResponse(path, media_type="audio/wav")
    raise HTTPException(501, f"TTS 미구현 — sample/server.py ensure_tts() 이식 예정 (text: {item['text']})")
