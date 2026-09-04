"""
B. 문제 생성 + 채점 (PRD 5.4)   담당: 팀장

POST /api/quiz   {student, level, unit, count}  → {quiz_id, questions[]}
POST /api/answer {student, quiz_id, question_id, choice} → {correct, answer}
생성 규칙: wrong_words 를 count 의 절반 이상 포함 · 나머지는 Unit 단어 무작위 · 각 문제는 RAG 조각 1개 근거
Gemini 응답은 JSON 스키마 강제, 파싱 실패 시 1회 재시도. 프롬프트: backend/prompts/quiz.txt
오답이면 data/student/wrong_words.json 에 누적, quiz_log.jsonl 에 기록.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["quiz"])


class QuizIn(BaseModel):
    student: str
    level: int
    unit: str
    count: int = 3


class AnswerIn(BaseModel):
    student: str
    quiz_id: str
    question_id: str
    choice: int


@router.post("/quiz")
def make_quiz(body: QuizIn):
    # TODO: golden.words + rag.search + wrong_words → Gemini → questions
    return {"quiz_id": "", "questions": []}


@router.post("/answer")
def answer(body: AnswerIn):
    # TODO: 채점 + 오답 기록
    return {"correct": False, "answer": 0}
