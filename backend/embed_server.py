"""GPU 서버에서 임베딩 모델을 API로 서빙하는 최소 스크립트 (whisper_server.py와 같은 패턴,
Ollama처럼 별도 프로세스로 nohup 실행). 이 프로젝트 앱이 임포트하는 파일이 아니다 —
서버에 이 파일 하나만 올려서 독립 실행한다.

서버에서 실행 (team2 전용 venv, torch+CUDA+sentence-transformers 필요):
    source ~/workspace/team2/elem-english-rag/.venv/bin/activate
    pip install fastapi uvicorn sentence-transformers
    nohup python embed_server.py > embed_server.log 2>&1 &

backend/embedding.py 쪽에서 쓰려면 .env 에 EMBEDDING_BACKEND=remote,
EMBEDDING_REMOTE_URL=http://192.168.1.147:8002 추가.

서버 하나당 모델 하나만 상시 로드한다(GPU 메모리 절약) — 다른 모델로 테스트하려면
EMBED_SERVER_MODEL 바꿔서 재시작. 2026-09-10 실측(hit@1, n=65) 기준 로컬 후보 중
최고는 intfloat/multilingual-e5-base(0.7231) — 기본값으로 지정해둠.
"""
import os

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMBED_SERVER_MODEL", "intfloat/multilingual-e5-base")
PORT = int(os.environ.get("EMBED_SERVER_PORT", "8002"))

app = FastAPI()
_model = SentenceTransformer(MODEL_NAME, device="cuda")


class EmbedIn(BaseModel):
    texts: list[str]
    task_type: str = "RETRIEVAL_DOCUMENT"   # "RETRIEVAL_DOCUMENT" | "RETRIEVAL_QUERY"


def _needs_e5_prefix(name: str) -> bool:
    return "e5-" in name


@app.post("/embed")
def embed(body: EmbedIn):
    texts = body.texts
    if _needs_e5_prefix(MODEL_NAME):
        prefix = "passage: " if body.task_type == "RETRIEVAL_DOCUMENT" else "query: "
        texts = [prefix + t for t in texts]
    vectors = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return {"embeddings": [[float(x) for x in v] for v in vectors], "model": MODEL_NAME}


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_NAME, "device": str(_model.device)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
