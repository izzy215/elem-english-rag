"""
초등 영어학습 · RAG 맞춤 복습 — FastAPI 진입점

실행 (작업 폴더 루트에서):
  python -m uvicorn backend.main:app --app-dir project --reload --port 8000

이 파일은 '연결'만 한다. 기능은 담당자별 파일에 있고, 여기서는 라우터를 모아 붙인다.
→ 세 사람이 각자 자기 파일만 고치므로 main.py 에서 충돌이 나지 않는다.

  golden.py   학습 데이터 (levels · units · words · sentences · progress)   TTS 팀원
  tts.py      D. 듣기                                                      TTS 팀원
  speak.py    E. 말하기 평가                                                TTS 팀원
  rag.py      A. RAG 검색 · 검수 경고 · 평가                                 RAG 팀원
  quiz.py     B. 문제 생성 · 채점                                            팀장
  explain.py  C. 오답 설명                                                  팀장
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import explain, golden, quiz, rag, speak, tts
from backend.config import settings

ROOT = Path(__file__).resolve().parent.parent          # project/
FRONT_DIR = ROOT / "frontend"
STUDENT_DIR = ROOT / "data" / "student"
STUDENT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="초등 영어 RAG 맞춤 복습 API", version="0.1")


@app.middleware("http")
async def no_cache(request, call_next):
    """개발 중엔 브라우저가 index.html / app.js 를 캐시하지 않게 한다."""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# 담당자별 라우터 — 새 기능은 파일 하나 만들고 여기 한 줄 추가
for r in (golden.router, tts.router, speak.router, rag.router, quiz.router, explain.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "api_key": settings.has_api_key,
        "model": settings.gemini_model,
        "golden_files": golden.golden_files(),
        "using_sample": golden.using_sample(),
    }


app.mount("/", StaticFiles(directory=FRONT_DIR, html=True), name="frontend")
