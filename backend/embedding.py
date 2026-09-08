"""
임베딩 — 실행 단위 ②   담당: RAG 담당

실행 단위 ①에서 로컬 기본(all-MiniLM-L6-v2) · 다국어 로컬 · Gemini(gemini-embedding-001) 세 후보를
_sample-B(규칙 8 · 평가 8)로 실측한 결과 hit@3 75%로 동률이었다. 성능 차이가 없어, API 키·과금이
필요 없는 Chroma 기본 임베딩(all-MiniLM-L6-v2, 완전 로컬)으로 확정한다(사용자 결정, 2026-09-08).
Gemini로 바꾸려면 이 파일의 _get_ef()/embed_* 구현만 교체하면 된다 — 호출부(rag.py·indexing.py)는
모델을 모른다.

문서/질의를 반드시 같은 검색 공간(같은 모델·같은 호출 방식)으로 임베딩해야 검색이 의미를 가진다.
all-MiniLM-L6-v2 는 Gemini 임베딩과 달리 문서/질의를 구분하는 task_type 이 없으므로 embed_documents 와
embed_query 는 내부적으로 같은 함수를 그대로 쓴다.
"""
from __future__ import annotations

EMBEDDING_PROVIDER = "chromadb-default"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # chromadb.utils.embedding_functions.DefaultEmbeddingFunction 고정 모델
EMBEDDING_DIM = 384

_ef = None


def _get_ef():
    """chromadb 기본 임베딩 함수. 첫 호출 때 모델 가중치를 로드한다(로컬 캐시, 최초 1회만 다운로드)."""
    global _ef
    if _ef is None:
        from chromadb.utils import embedding_functions
        _ef = embedding_functions.DefaultEmbeddingFunction()
    return _ef


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _get_ef()(texts)
    return [[float(x) for x in v] for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_documents([text])[0]
