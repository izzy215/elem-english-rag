"""
D. TTS (PRD 5.2)   담당: TTS 팀원

사용법:

    GET /api/tts/{item_id}
    → 200: audio/wav 바이너리 (그대로 <audio src="/api/tts/{item_id}"> 나 fetch 로 재생)
    → 404: {"detail": "단어/문장 없음"}   item_id 가 golden 데이터(words.csv/sentences.csv)에 없을 때
    → 500: GEMINI_API_KEY 미설정

    item_id 는 words.csv/sentences.csv 의 id (예: "w-0031", "s-0012").
    최초 호출은 음성 생성 때문에 몇 초 걸릴 수 있고, 이후 같은 id는 캐시라 즉시 응답할겁니다
"""
import wave
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

from backend import golden
from backend.config import settings

router = APIRouter(tags=["tts"])

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _save_wav(path: Path, pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def ensure_tts(item_id: str, text: str) -> Path:
    path = settings.audio_cache_dir / f"{item_id}.wav"
    if path.exists():
        return path

    if not settings.has_api_key:
        raise HTTPException(500, "GEMINI_API_KEY 가 설정되어 있지 않음")

    response = _get_client().models.generate_content(
        model=settings.gemini_tts_model,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=settings.gemini_tts_voice,
                    )
                )
            ),
        ),
    )
    pcm = response.candidates[0].content.parts[0].inline_data.data
    _save_wav(path, pcm)
    return path


@router.get("/tts/{item_id}")
def tts(item_id: str):
    item = golden.find_item(item_id)
    if not item:
        raise HTTPException(404, "단어/문장 없음")
    path = ensure_tts(item_id, item["text"])
    return FileResponse(path, media_type="audio/wav")
