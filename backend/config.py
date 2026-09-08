"""
환경설정 로더.
프로젝트 루트의 .env 파일을 읽어 설정값을 한 곳에서 제공한다.

다른 파일에서는 이렇게 쓴다:
    from config import settings
    settings.gemini_api_key
    settings.gemini_model

.env 가 없으면 .env.example 을 복사해서 만들 것.
"""
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent   # project/ (backend/ 의 상위)
ENV_FILE = ROOT / ".env"

# .env 가 있으면 읽고, 없으면 시스템 환경변수만 사용 (setx로 넣은 값도 그대로 동작)
load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gemini_tts_model: str
    gemini_tts_voice: str
    app_title: str
    learner_name: str
    audio_cache_dir: Path
    # LLM 제공자 (backend/llm.py)
    llm_backend: str = "gemini"
    llm_local_url: str = ""
    llm_local_model: str = ""
    llm_local_api_key: str = ""
    llm_timeout: float = 30.0
    llm_fallback: bool = True

    @property
    def has_api_key(self) -> bool:
        return bool(self.gemini_api_key) and not self.gemini_api_key.startswith("여기에")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


settings = Settings(
    gemini_api_key=_get("GEMINI_API_KEY"),
    gemini_model=_get("GEMINI_MODEL", "gemini-3.6-flash"),
    gemini_tts_model=_get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
    gemini_tts_voice=_get("GEMINI_TTS_VOICE", "Kore"),
    app_title=_get("APP_TITLE", "에코"),
    learner_name=_get("LEARNER_NAME", "지수"),
    audio_cache_dir=ROOT / _get("AUDIO_CACHE_DIR", "audio_cache"),
    llm_backend=_get("LLM_BACKEND", "gemini").lower(),
    llm_local_url=_get("LLM_LOCAL_URL"),
    llm_local_model=_get("LLM_LOCAL_MODEL", "qwen2.5:7b-instruct"),
    llm_local_api_key=_get("LLM_LOCAL_API_KEY"),
    llm_timeout=float(_get("LLM_TIMEOUT", "30") or 30),
    llm_fallback=_get("LLM_FALLBACK", "1") not in ("0", "false", "no"),
)


if __name__ == "__main__":
    # python config.py 로 실행하면 설정이 제대로 읽히는지 확인
    print(f".env 파일: {'있음' if ENV_FILE.exists() else '없음 (.env.example을 복사하세요)'}")
    print(f"API 키:    {'설정됨 (' + settings.gemini_api_key[:6] + '...)' if settings.has_api_key else '없음'}")
    print(f"모델:      {settings.gemini_model} / TTS {settings.gemini_tts_model} ({settings.gemini_tts_voice})")
    print(f"앱 제목:   {settings.app_title} · 학습자 {settings.learner_name}")
    print(f"음원 캐시: {settings.audio_cache_dir}")
