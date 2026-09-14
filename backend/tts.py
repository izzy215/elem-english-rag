"""
D. TTS (PRD 5.2)   담당: TTS 팀원

사용법:

    GET /api/tts/{item_id}
    → 200: audio/wav 바이너리 (그대로 <audio src="/api/tts/{item_id}"> 나 fetch 로 재생)
    → 404: {"detail": "단어/문장 없음"}   item_id 가 golden 데이터(words.csv/patterns.csv)에 없을 때
    → 500: Piper 보이스 모델을 다운로드하지 못했을 때 (네트워크 없음 등)

    item_id 는 words.csv/patterns.csv 의 id (예: "w-0031", "s-0012").
    Piper는 로컬 ONNX 모델로 오프라인 합성(API 키/quota 불필요). 보이스 모델이 없으면
    (PIPER_VOICE_DIR에) 처음 한 번만 자동으로 받아오고, 이후엔 완전 오프라인으로 동작함.
    같은 item_id는 캐시된 wav를 그대로 응답함.
"""
import wave
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from piper import PiperVoice
from piper.download_voices import download_voice

from backend import golden
from backend.config import settings

router = APIRouter(tags=["tts"])

_voice: PiperVoice | None = None


def _voice_model_path() -> Path:
    return settings.piper_voice_dir / f"{settings.piper_voice_name}.onnx"


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        model_path = _voice_model_path()
        if not model_path.exists():
            settings.piper_voice_dir.mkdir(parents=True, exist_ok=True)
            try:
                download_voice(settings.piper_voice_name, settings.piper_voice_dir)
            except Exception as e:
                raise HTTPException(500, f"Piper 보이스 모델({settings.piper_voice_name}) 다운로드 실패: {e}")
        _voice = PiperVoice.load(model_path, use_cuda=settings.piper_use_cuda)
    return _voice


def ensure_tts(item_id: str, text: str) -> Path:
    path = settings.audio_cache_dir / f"{item_id}.wav"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".wav.tmp")
    with wave.open(str(tmp_path), "wb") as wf:
        _get_voice().synthesize_wav(text, wf)
    tmp_path.replace(path)  # 합성 도중 실패해도 손상된 파일이 캐시로 남지 않게
    return path


@router.get("/tts/{item_id}")
def tts(item_id: str):
    item = golden.find_item(item_id)
    if not item:
        raise HTTPException(404, "단어/문장 없음")
    path = ensure_tts(item_id, item["text"])
    return FileResponse(path, media_type="audio/wav")
