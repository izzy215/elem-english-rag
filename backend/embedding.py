"""
임베딩 — 실행 단위 ②   담당: RAG 담당

Gemini 임베딩(gemini-embedding-001)을 사용한다. 문서와 질의를 task_type으로
구분해 같은 검색 공간에 임베딩한다.
"""
from __future__ import annotations

import math

from backend.config import settings

EMBEDDING_PROVIDER = "google-genai"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
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


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _embed([text], "RETRIEVAL_QUERY")[0]
