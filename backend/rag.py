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
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import indexing, embedding, golden

router = APIRouter(prefix="/rag", tags=["rag"])

K_MIN, K_MAX = 1, 10   # 현재 규칙 8개 기준 여유 있게 잡은 상한. 데이터가 늘면 재검토

# 2026-09-10 실험(docs/RAG_0910/Claude/Phase2-개선실험결과.md)으로 확인: R-01은 예문을 26개 다
# 넣어도, 모델을 로컬→Gemini로 바꿔도 임베딩 순위에서 계속 빠진다 — "형용사 앞 be동사 누락"은
# 의미가 아니라 단어 하나가 빠졌는지의 구조 문제라 문장 임베딩이 원래 못 잡는 유형으로 판단된다.
# 순수 임베딩 검색에 못 걸리는 걸 알고 있는 규칙만, 얕은 키워드 조건으로 안전망을 둔다 — 모든
# 검색에 끼워넣는 게 아니라 "이 규칙이 실제로 관련 있을 가능성이 있는 문장"일 때만 작동한다.
_LEXICAL_SAFETY_NET: dict[str, dict[str, set[str]]] = {
    "R-01": {
        # errors.jsonl 의 R-01 오답 예문(26개)에서 실제로 쓰인 형용사 — 임의 확장이 아니라 데이터 근거
        "trigger": {
            "sorry", "polite", "formal", "endangered", "colorful", "bright", "pale", "vivid",
            "humid", "foggy", "seasonal", "annual", "temperate", "punctual", "urban", "happy",
            "sad", "angry", "tired", "hungry", "excited", "scared", "surprised", "bored",
            "nervous", "spacious",
        },
        # be동사가 이미 있으면 "빠진" 문장이 아니므로 안전망을 걸지 않는다
        "exclude": {"am", "is", "are", "was", "were", "be", "being", "been"},
    },
}


def _apply_lexical_safety_net(text: str, ranked: list[dict], out: list[dict]) -> list[dict]:
    """임베딩 top-k에서 빠졌지만 얕은 키워드 조건에 맞는 안전망 규칙을, 전체 순위(ranked)에
    실제로 있으면(즉 색인엔 있고 실제 cosine 점수도 있으면) 실제 점수 그대로 out 뒤에 추가한다.
    가짜 점수를 만들지 않는다 — ranked 에 없는 규칙은 추가하지 않는다."""
    present = {c["id"] for c in out}
    tokens = set(re.findall(r"[a-zA-Z']+", text.lower()))
    for rule_id, cond in _LEXICAL_SAFETY_NET.items():
        if rule_id in present:
            continue
        if not (tokens & cond["trigger"]):
            continue
        if tokens & cond.get("exclude", set()):
            continue
        boosted = next((c for c in ranked if c["id"] == rule_id), None)
        if boosted:
            out = out + [boosted]
    return out


def search_rules(text: str, k: int = 3) -> list[dict]:
    """id, type, text, unit, score(=1-cosine_distance) 후보를 score 내림차순으로 반환.
    색인이 없거나 검색 도중 실패하면(컬렉션 접근·임베딩·질의 전부 포함) indexing.IndexUnavailableError
    로 정규화해서 올린다 — 호출부(HTTP 계층의 503 매핑, tutor.py의 폴백 전환)가 이 예외 하나만
    잡으면 되도록 하기 위함. 원인 예외는 `raise ... from e`로 보존된다.

    반환 길이는 보통 k 이지만, _LEXICAL_SAFETY_NET 에 걸리는 문장이면 k+1 이 될 수 있다(임베딩
    순위 밖의 안전망 규칙 1개를 실제 점수와 함께 추가) — 호출부는 상위 몇 개만 쓰면 되므로 길이를
    정확히 k 로 가정하지 않아야 한다."""
    manifest = indexing.load_manifest()
    client = indexing._chroma_client()  # noqa: SLF001 — indexing 모듈이 Chroma 연결의 유일한 소유자라 그대로 재사용
    try:
        col = client.get_collection(manifest["active_collection"])
        n = max(1, min(k, manifest["count"]))   # 저장 건수를 넘는 후보 수를 요청해도 초과 반환하지 않음
        qvec = embedding.embed_query(text)
        # 안전망 규칙이 전체 순위 어디에 있는지도 봐야 하므로, 표시할 개수(n)와 별개로 전체를 받아둔다
        res = col.query(query_embeddings=[qvec], n_results=manifest["count"])
    except indexing.IndexUnavailableError:
        raise
    except Exception as e:
        raise indexing.IndexUnavailableError(f"검색 실패(컬렉션 접근·임베딩·질의 중): {e}") from e
    if not res["ids"] or not res["ids"][0]:
        return []
    ranked = []
    for id_, dist, doc, meta in zip(res["ids"][0], res["distances"][0], res["documents"][0], res["metadatas"][0]):
        ranked.append({"id": id_, "type": meta.get("type"), "text": doc, "unit": meta.get("unit"), "score": round(1 - dist, 4)})
    out = ranked[:n]   # col.query 가 이미 거리 오름차순(=score 내림차순)으로 반환
    return _apply_lexical_safety_net(text, ranked, out)


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
