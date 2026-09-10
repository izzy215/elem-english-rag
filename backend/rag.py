"""
RAG 검색   담당: RAG 담당

  GET  /api/rag/search?q=&level=&k=   학생 문장/질문 → 관련 규칙 조각 상위 k개 (실제 구현, 실행 단위 ②)
  POST /api/rag/check {text, level}   검수 경고 — PRD-B 범위 밖(A안 잔재), 스텁 유지. 손대지 않음
  GET  /api/rag/eval                  검색 평가 결과 조회 — 실행 단위 ③에서 구현 예정. 스텁 유지

색인·임베딩은 backend/indexing.py(색인 생성) · backend/embedding.py(임베딩 함수)가 맡는다. 이 파일은
그 결과(backend/indexing.load_manifest() 가 가리키는 Chroma 컬렉션)를 읽어 검색만 한다 — API 조회 시
색인을 새로 만들지 않는다.

기존 계약 유지: 최상위 키는 `query`/`chunks`(PRD 초안의 `hits`가 아님), 입력은 `q`/`level`/`k`
그대로(`level`은 필터 미적용 — 여러 Unit이 공유하는 규칙을 누락시키지 않기 위함, 실행 단위 ①에서
확정). `threshold`는 이번 기준선에서 값 없이 필드만 유지한다.
"""
from __future__ import annotations

import json
import hashlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import indexing, embedding, golden

router = APIRouter(prefix="/rag", tags=["rag"])

K_MIN, K_MAX = 1, 10   # 현재 규칙 8개 기준 여유 있게 잡은 상한. 데이터가 늘면 재검토


def search_rules(text: str, k: int = 3) -> list[dict]:
    """id, type, text, unit, score(=1-cosine_distance) 후보를 score 내림차순으로 반환.
    색인이 없거나 검색 도중 실패하면(컬렉션 접근·임베딩·질의 전부 포함) indexing.IndexUnavailableError
    로 정규화해서 올린다 — 호출부(HTTP 계층의 503 매핑, tutor.py의 폴백 전환)가 이 예외 하나만
    잡으면 되도록 하기 위함. 원인 예외는 `raise ... from e`로 보존된다.

    반환 길이는 요청한 k 이내다."""
    manifest = indexing.load_manifest()
    client = indexing._chroma_client()  # noqa: SLF001 — indexing 모듈이 Chroma 연결의 유일한 소유자라 그대로 재사용
    try:
        col = client.get_collection(manifest["active_collection"])
        n = max(1, min(k, manifest["count"]))   # 저장 건수를 넘는 후보 수를 요청해도 초과 반환하지 않음
        qvec = embedding.embed_query(text)
        res = col.query(query_embeddings=[qvec], n_results=n)
    except indexing.IndexUnavailableError:
        raise
    except Exception as e:
        raise indexing.IndexUnavailableError(f"검색 실패(컬렉션 접근·임베딩·질의 중): {e}") from e
    if not res["ids"] or not res["ids"][0]:
        return []
    ranked = []
    for id_, dist, doc, meta in zip(res["ids"][0], res["distances"][0], res["documents"][0], res["metadatas"][0]):
        ranked.append({"id": id_, "type": meta.get("type"), "text": doc, "unit": meta.get("unit"), "score": round(1 - dist, 4)})
    return ranked


@router.get("/search")
def search(q: str, level: int | None = None, k: int = 3):
    q = q.strip()
    if not (1 <= len(q) <= 1000):
        raise HTTPException(422, "q 는 공백 제거 후 1~1000자여야 함")
    if not (K_MIN <= k <= K_MAX):
        raise HTTPException(422, f"k 는 {K_MIN}~{K_MAX} 사이여야 함")

    try:
        chunks = search_rules(q, k=k)
    except indexing.IndexUnavailableError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:  # noqa: BLE001 — 임베딩·Chroma 쪽 예외 유형을 전부 예측할 수 없어 그대로 503으로 구분
        raise HTTPException(503, f"검색 서비스 오류: {e}") from e

    return {"query": q, "chunks": chunks, "threshold": None, "score_type": "cosine_similarity"}


@router.post("/check")
def check(body: CheckIn):
    # TODO: golden words 에 없는 단어 → "범위 밖 단어: x", search score ≥ 0.85 → "유사 문장 nn%: ..."
    # PRD-B 4.2 범위 밖(A안 잔재) — v0.2 work order가 이번 범위 제외로 명시. 손대지 않음.
    return {"ok": True, "warnings": []}


@router.get("/eval")
def evaluate():
    """저장된 검색 평가 결과만 읽는다. 조회 자체는 임베딩·검색을 새로 실행하지 않는다.
    실제 평가는 `python -m tests.eval_rag --retrieval-only` 로 실행한다(RAG 담당)."""
    path = indexing.RETRIEVAL_EVAL_LATEST
    if not path.exists():
        return {"n": 0, "hit_at_3": None, "hit_at_1": None, "runs": []}

    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        manifest = indexing.load_manifest()
        recorded_index = data.get("index") or {}
        stale = manifest["data_hash"] != data.get("data_hash")
        stale |= any(recorded_index.get(key) != manifest.get(key) for key in
                     ("active_collection", "provider", "model", "dim", "distance", "text_version"))
        stale |= manifest["data_hash"] != indexing._data_hash(golden.rules())
        stale |= (manifest.get("provider"), manifest.get("model"), manifest.get("dim")) != (
            embedding.EMBEDDING_PROVIDER, embedding.EMBEDDING_MODEL, embedding.EMBEDDING_DIM)
        eval_hash = hashlib.sha256(json.dumps(golden.eval_set(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        stale |= eval_hash != data.get("evaluation_hash")
    except indexing.IndexUnavailableError:
        stale = True   # 색인 자체가 없으면 평가 결과가 지금 색인을 반영한다고 볼 수 없음
    data["stale"] = stale
    return data
