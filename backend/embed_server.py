"""GPU 서버에서 임베딩 모델을 API로 서빙하는 최소 스크립트 (whisper_server.py와 같은 패턴,
Ollama처럼 별도 프로세스로 nohup 실행). 이 프로젝트 앱이 임포트하는 파일이 아니다 —
서버에 이 파일 하나만 올려서 독립 실행한다.

서버에서 실행 (team2 전용 venv, torch+CUDA+sentence-transformers 필요):
    source ~/workspace/team2/elem-english-rag/.venv/bin/activate
    pip install fastapi uvicorn sentence-transformers
    USE_TF=0 nohup python embed_server.py > embed_server.log 2>&1 &

`USE_TF=0` 필수 — 이 venv에 다른 작업(YOLO 등)이 설치해둔 TensorFlow가 같이 있으면,
`sentence_transformers`가 import 시 TensorFlow도 같이 로드하려다 torch와 네이티브 라이브러리
충돌로 세그폴트(코어 덤프)가 난다(2026-09-18 실측 — GPU/CPU 둘 다 재현, torch 단독·tensorflow
단독은 각각 멀쩡했음). `USE_TF=0`으로 transformers가 TensorFlow 백엔드를 아예 안 건드리게
막으면 해결됨.

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

/rerank 엔드포인트(크로스인코더 재랭킹, 2026-09-11 추가) — tests/rerank_compare.py 등이 로컬
CPU 대신 이 서버 GPU를 쓰게 함(로컬 CPU로 돌리면 느리고 메모리 부족 에러도 남). 기본 모델은
BAAI/bge-reranker-v2-m3(다국어, bge-m3와 같은 계열).
"""
import os

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder

DEFAULT_MODEL = os.environ.get("EMBED_SERVER_MODEL", "intfloat/multilingual-e5-base")
DEFAULT_RERANKER = os.environ.get("EMBED_SERVER_RERANKER", "BAAI/bge-reranker-v2-m3")
PORT = int(os.environ.get("EMBED_SERVER_PORT", "8002"))
DEVICE = os.environ.get("EMBED_SERVER_DEVICE", "cuda:0")

app = FastAPI()
_models: dict[str, "SentenceTransformer"] = {}   # 모델 이름별 캐시 — 팀원마다 다른 모델 요청해도 한 번만 로드
_rerankers: dict[str, "CrossEncoder"] = {}       # 재랭커도 모델 이름별로 따로 캐시


def _get_model(name: str):
    if name not in _models:
        _models[name] = SentenceTransformer(name, device=DEVICE)
    return _models[name]


def _get_reranker(name: str):
    if name not in _rerankers:
        _rerankers[name] = CrossEncoder(name, device=DEVICE)
    return _rerankers[name]


class EmbedIn(BaseModel):
    texts: list[str]
    task_type: str = "RETRIEVAL_DOCUMENT"   # "RETRIEVAL_DOCUMENT" | "RETRIEVAL_QUERY"
    model: str = DEFAULT_MODEL


class RerankIn(BaseModel):
    query: str
    candidates: list[str]
    model: str = DEFAULT_RERANKER


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


@app.post("/rerank")
def rerank(body: RerankIn):
    reranker = _get_reranker(body.model)
    pairs = [[body.query, c] for c in body.candidates]
    scores = reranker.predict(pairs)
    return {"scores": [float(s) for s in scores], "model": body.model}


@app.get("/health")
def health():
    return {"ok": True, "models_loaded": list(_models.keys()), "rerankers_loaded": list(_rerankers.keys()),
            "default_model": DEFAULT_MODEL, "default_reranker": DEFAULT_RERANKER, "device": DEVICE}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
