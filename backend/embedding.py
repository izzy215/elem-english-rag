"""
임베딩 — 실행 단위 ②   담당: RAG 담당

실행 단위 ①에서 로컬 기본(all-MiniLM-L6-v2) · 다국어 로컬 · Gemini(gemini-embedding-001) 세 후보를
_sample-B(규칙 8 · 평가 8)로 실측했을 때는 hit@3 75%로 동률이라 로컬 모델을 채택했다(2026-09-08).
데이터팀 정식 납품(실데이터 38규칙 · 평가 72문항) 이후 재측정한 결과 gemini-embedding-001이
hit@1 70.77%→76.92%, hit@3 87.69%→89.23%로 로컬 모델을 뚜렷이 앞서 목표(hit@1≥75%)를 달성했다
(2026-09-10 회의 후속 실험, docs/RAG_0910/Claude/Phase2-개선실험결과.md). 이에 따라 Gemini로 전환한다.

GEMINI_API_KEY 필요. 문서/질의를 task_type으로 구분해서 호출한다. free tier는 분당 요청 수 제한이
있어 색인 재구축(규칙 수십 건)·다수 동시 검색 시 429(RESOURCE_EXHAUSTED)가 날 수 있는데, 별도 재시도
로직을 여기 두지 않는다 — rag.py의 search_rules()가 이 모듈에서 나는 예외를 전부
IndexUnavailableError로 정규화해 tutor.py가 이미 전체 규칙 폴백으로 처리하기 때문이다. 같은 이유로
클라이언트 자체 재시도도 1회로 제한한다(`retry_options`) — 학생이 기다리는 요청이라 계속 재시도하기
보다 빨리 실패해서 폴백으로 넘어가는 게 낫다.

응답 검증: 개수·차원·유한값·영벡터를 확인해 이상 응답이 조용히 잘못된 검색으로 이어지지 않게 한다
(빈 배열·차원 불일치·NaN·전부 0인 벡터는 ValueError로 즉시 실패 → 위와 같은 경로로 폴백).
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
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"timeout": 15000, "retry_options": {"attempts": 1}},
        )
    return _client


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    resp = _get_client().models.embed_content(
        model=EMBEDDING_MODEL, contents=texts, config={"task_type": task_type},
    )
    vectors = [list(e.values) for e in (resp.embeddings or [])]
    if len(vectors) != len(texts):
        raise ValueError("Gemini embedding response count mismatch")
    if any(len(v) != EMBEDDING_DIM or not all(math.isfinite(x) for x in v)
           or not any(v) for v in vectors):
        raise ValueError("Gemini embedding response has invalid dimension or values")
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _embed([text], "RETRIEVAL_QUERY")[0]
