"""
임베딩 — 실행 단위 ②   담당: RAG 담당

EMBEDDING_BACKEND(.env)로 임베딩 소스를 고른다 — 팀원마다 API 키·서버 상황이 달라서
gemini(기본, RAG팀 확정)/local(각자 PC, API 불필요)/remote(강의실 서버 GPU, 7개 모델 상시
캐시됨) 중 하나를 실제 운영 환경에서 골라 쓸 수 있게 했다(2026-09-11, 팀 합의).

    EMBEDDING_BACKEND=gemini   (기본값) gemini-embedding-001, GEMINI_API_KEY 필요
    EMBEDDING_BACKEND=local    sentence-transformers 로컬 실행(EMBEDDING_LOCAL_MODEL로 모델
                               지정, pip install sentence-transformers 필요)
    EMBEDDING_BACKEND=remote   강의실 서버의 backend/embed_server.py를 HTTP로 호출
                               (EMBEDDING_REMOTE_URL, EMBEDDING_REMOTE_MODEL)

문서/질의를 반드시 같은 검색 공간(같은 백엔드·같은 모델)으로 임베딩해야 검색이 의미를 가진다 —
백엔드를 바꾸면 반드시 `python -m backend.indexing --rebuild`로 색인을 다시 만들어야 한다.

2026-09-11 실측(hit@1, n=65, 재랭킹 없는 순수 검색 기준, 참고용):
gemini 76.92%(RAG팀 확정) · multilingual-e5-base 72.31% · all-MiniLM-L6-v2 70.77% ·
multilingual-e5-large 69.23% · all-mpnet-base-v2 61.54% · BAAI/bge-m3 60.00% ·
paraphrase-multilingual-mpnet-base-v2/MiniLM-L12-v2 55.38%
"""
from __future__ import annotations

import math
import os

from backend.config import settings


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


BACKEND = _env("EMBEDDING_BACKEND", "gemini").lower()

# 모델별 차원 — 첫 호출 전에도 EMBEDDING_DIM이 정확한 값을 갖도록(모르는 모델이면 0, 첫 호출 후 갱신).
_KNOWN_DIMS = {
    "gemini-embedding-001": 3072,
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "paraphrase-multilingual-mpnet-base-v2": 768,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,
    "BAAI/bge-m3": 1024,
}

if BACKEND == "gemini":
    EMBEDDING_PROVIDER = "google-genai"
    EMBEDDING_MODEL = "gemini-embedding-001"
elif BACKEND == "local":
    EMBEDDING_PROVIDER = "sentence-transformers-local"
    EMBEDDING_MODEL = _env("EMBEDDING_LOCAL_MODEL", "intfloat/multilingual-e5-base")
elif BACKEND == "remote":
    EMBEDDING_PROVIDER = "remote-http"
    EMBEDDING_MODEL = _env("EMBEDDING_REMOTE_MODEL", "intfloat/multilingual-e5-base")
else:
    raise ValueError(f"알 수 없는 EMBEDDING_BACKEND: {BACKEND!r} (gemini/local/remote 중 하나)")

EMBEDDING_DIM = _KNOWN_DIMS.get(EMBEDDING_MODEL, 0)


# ── gemini ──────────────────────────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _embed_gemini(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    response = _get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config={"task_type": task_type},
    )
    vectors = [list(item.values) for item in (response.embeddings or [])]
    if len(vectors) != len(texts):
        raise ValueError("Gemini embedding response count mismatch")
    if any(
        len(vector) != EMBEDDING_DIM
        or not all(math.isfinite(value) for value in vector)
        or not any(vector)
        for vector in vectors
    ):
        raise ValueError("Gemini embedding response has invalid dimension or values")
    return vectors


# ── local (sentence-transformers, 팀원 각자 PC — pip install sentence-transformers 필요) ──
_st_model = None


def _needs_e5_prefix(name: str) -> bool:
    return "e5-" in name


def _get_st_model():
    global _st_model, EMBEDDING_DIM
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer(EMBEDDING_MODEL)
        get_dim = getattr(_st_model, "get_embedding_dimension", _st_model.get_sentence_embedding_dimension)
        EMBEDDING_DIM = get_dim()
    return _st_model


def _embed_local(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    model = _get_st_model()
    if _needs_e5_prefix(EMBEDDING_MODEL):
        prefix = "passage: " if task_type == "RETRIEVAL_DOCUMENT" else "query: "
        texts = [prefix + t for t in texts]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [[float(x) for x in v] for v in vectors]


# ── remote (강의실 서버 GPU, backend/embed_server.py 호출) ───────────
def _embed_remote(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    import requests
    global EMBEDDING_DIM
    url = _env("EMBEDDING_REMOTE_URL", "http://192.168.1.147:8002").rstrip("/") + "/embed"
    resp = requests.post(url, json={"texts": texts, "task_type": task_type, "model": EMBEDDING_MODEL}, timeout=60)
    resp.raise_for_status()
    vectors = resp.json()["embeddings"]
    if vectors:
        EMBEDDING_DIM = len(vectors[0])
    return vectors


_IMPL = {"gemini": _embed_gemini, "local": _embed_local, "remote": _embed_remote}[BACKEND]


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _IMPL(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _IMPL([text], "RETRIEVAL_QUERY")[0]
