"""
A. RAG (PRD 5.3)   담당: RAG 팀원

인덱스 하나, 입구 둘:
  GET  /api/rag/search?q=&level=&k=   학습용 ○  → 교재 조각 k개 (quiz · explain 의 근거)
  POST /api/rag/check {text, level}   검수용 ○  → 범위 밖 단어 · 유사 문장 경고
  GET  /api/rag/eval                  평가     → eval.csv 기준 hit@3 · 실험 이력
데이터: data/golden/chunks.jsonl (id, text, level, unit, source_page, word_ids)
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/rag", tags=["rag"])


class CheckIn(BaseModel):
    text: str
    level: int


@router.get("/search")
def search(q: str, level: int | None = None, k: int = 3):
    # TODO: 임베딩 + FAISS. chunks: [{id, text, level, unit, source_page, score}]
    return {"query": q, "chunks": []}


@router.post("/check")
def check(body: CheckIn):
    # TODO: golden words 에 없는 단어 → "범위 밖 단어: x", search score ≥ 0.85 → "유사 문장 nn%: ..."
    return {"ok": True, "warnings": []}


@router.get("/eval")
def evaluate():
    # TODO: tests/ 에서 eval.csv 돌린 결과 저장 → 여기서 읽기
    return {"n": 0, "hit_at_3": None, "hit_at_1": None, "runs": []}
