"""
C. 오답 설명 (PRD 5.4)   담당: 팀장

POST /api/explain {student, quiz_id, question_id}
→ {explanation, source:{chunk_id, page, text}}
규칙: 초등 3학년 어휘로 2~3문장 · 반드시 source 포함 · 조각에 없는 내용 금지. 프롬프트: backend/prompts/explain.txt
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["explain"])


class ExplainIn(BaseModel):
    student: str
    quiz_id: str
    question_id: str


@router.post("/explain")
def explain(body: ExplainIn):
    # TODO: quiz_log 에서 문제 찾기 → rag.search(word) → Gemini → 설명 + 출처
    return {"explanation": "", "source": {"chunk_id": None, "page": None, "text": ""}}
