"""GPU 서버에서 임베딩 모델을 API로 서빙하는 최소 스크립트 (whisper_server.py와 같은 패턴,
Ollama처럼 별도 프로세스로 nohup 실행). 이 프로젝트 앱이 임포트하는 파일이 아니다 —
서버에 이 파일 하나만 올려서 독립 실행한다.

서버에서 실행 (team2 전용 venv, torch+CUDA+sentence-transformers 필요):
    source ~/workspace/team2/elem-english-rag/.venv/bin/activate
    pip install fastapi uvicorn sentence-transformers
    nohup python embed_server.py > embed_server.log 2>&1 &

팀원마다 원하는 모델을 요청에서 골라 쓸 수 있다(whisper_server.py의 모델 이름별 캐시와 동일한
패턴) — 서버 재시작 없이 여러 모델을 동시에 테스트 가능. 단, 모델마다 GPU 메모리를 새로 쓰니
너무 많은 대형 모델을 한꺼번에 캐시하면 GPU 메모리가 부족해질 수 있다(필요하면 서버 재시작으로
캐시 비우기). tests/embedding_backend_compare.py --backend remote --model <이름> 으로 지정.

2026-09-10 로컬 실측(hit@1, n=65) 기준 로컬 후보 중 최고는 intfloat/multilingual-e5-base
(0.7231) — 요청에 model을 안 주면 이걸 기본값으로 씀.

GPU는 EMBED_SERVER_DEVICE로 고른다(기본 cuda:0) — 이 서버는 team1의 Ollama·다른 실험과
같은 장비를 공유해서, GPU 0이 다른 팀 작업으로 이미 꽉 차 있으면 큰 모델 로드가 CUDA OOM으로
실패한다(2026-09-11, e5-large·bge-m3에서 발생). `nvidia-smi`로 여유 있는 GPU 번호를 확인해
EMBED_SERVER_DEVICE=cuda:1 처럼 지정하고 재시작.
"""
import os

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = os.environ.get("EMBED_SERVER_MODEL", "intfloat/multilingual-e5-base")
PORT = int(os.environ.get("EMBED_SERVER_PORT", "8002"))
DEVICE = os.environ.get("EMBED_SERVER_DEVICE", "cuda:0")

app = FastAPI()
_models: dict[str, "SentenceTransformer"] = {}   # 모델 이름별 캐시 — 팀원마다 다른 모델 요청해도 한 번만 로드


def _get_model(name: str):
    if name not in _models:
        _models[name] = SentenceTransformer(name, device=DEVICE)
    return _models[name]


class EmbedIn(BaseModel):
    texts: list[str]
    task_type: str = "RETRIEVAL_DOCUMENT"   # "RETRIEVAL_DOCUMENT" | "RETRIEVAL_QUERY"
    model: str = DEFAULT_MODEL


def _needs_e5_prefix(name: str) -> bool:
    return "e5-" in name


@app.post("/embed")
def embed(body: EmbedIn):
    model = _get_model(body.model)
    texts = body.texts
    if _needs_e5_prefix(body.model):
        prefix = "passage: " if body.task_type == "RETRIEVAL_DOCUMENT" else "query: "
        texts = [prefix + t for t in texts]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return {"embeddings": [[float(x) for x in v] for v in vectors], "model": body.model}


@app.get("/health")
def health():
    return {"ok": True, "models_loaded": list(_models.keys()), "default_model": DEFAULT_MODEL, "device": DEVICE}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
