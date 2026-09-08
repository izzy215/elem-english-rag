"""
규칙 연습 — 오답노트의 [이 규칙 연습하기] (PRD 4.4 · 7)   담당: 팀장

GET  /api/drill?student=A&rule=R-01&count=2
  → {drill_id, rule_id, rule_name, questions:[{id, sentence, target, choices}]}     (정답 위치는 서버만 안다)
POST /api/drill/answer {student, drill_id, question_id, choice}
  → {correct, answer, rule_text, done, all_correct, streak}

재료: errors.jsonl 한 줄 = 문제 하나 (error 문장, target 밑줄 단어, fix 정답, distractors 오답 3개)
판정: 한 묶음(count 문제)을 전부 맞히면 notebook streak +1, 하나라도 틀리면 0. streak 2 = 극복 (PRD 7)
기록: data/student/drill_log.jsonl (한 문제당 한 줄), notebook.json 의 streak

규칙·오답노트 파일 읽고 쓰는 함수는 tutor.py 것을 같이 쓴다 (골든 데이터 공통 함수가 golden.py 로 옮겨지면 같이 옮긴다).
Gemini 를 쓰지 않는다.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.tutor import STUDENT_DIR, _golden_path, _lock, find_rule

router = APIRouter(tags=["drill"])

OVERCOME_STREAK = 2          # 연속 2회 전부 정답 = 극복
_drills: dict[str, dict] = {}  # 진행 중인 묶음 (서버 메모리. 재시작하면 사라지므로 화면은 다시 [연습하기] 로 시작)
_MAX_DRILLS = 500


# ─────────────────────────────────────────────
# 데이터
# ─────────────────────────────────────────────
def errors() -> list[dict]:
    path = _golden_path("errors.jsonl")
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _log(row: dict) -> None:
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, (STUDENT_DIR / "drill_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _update_streak(student: str, rule_id: str, all_correct: bool) -> int:
    """notebook.json 의 해당 규칙 streak 갱신. 오답노트에 없는 규칙이면 건드리지 않는다 (극복할 게 없음)."""
    path = STUDENT_DIR / "notebook.json"
    with _lock:
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data.get(student, {}).get(rule_id)
        if not entry:
            return 0
        entry["streak"] = min(OVERCOME_STREAK, entry.get("streak", 0) + 1) if all_correct else 0
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return entry["streak"]


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
@router.get("/drill")
def get_drill(student: str, rule: str, count: int = 2):
    rule_doc = find_rule(rule)
    pool = [e for e in errors() if e.get("rule_id") == rule]
    if not pool:
        raise HTTPException(404, f"{rule} 의 연습 문제가 없음 (errors.jsonl)")
    picked = random.sample(pool, min(count, len(pool)))

    questions = []
    for i, e in enumerate(picked):
        choices = [e["fix"]] + list(e.get("distractors", []))[:3]
        random.shuffle(choices)
        questions.append({
            "id": f"d{i + 1}", "error_id": e["id"], "sentence": e["error"], "target": e["target"],
            "choices": choices, "answer": choices.index(e["fix"]), "answered": None,
        })

    drill_id = "D-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    if len(_drills) >= _MAX_DRILLS:                       # 오래된 것부터 정리
        for k in list(_drills)[: _MAX_DRILLS // 2]:
            _drills.pop(k, None)
    _drills[drill_id] = {"student": student, "rule_id": rule, "questions": questions}

    return {
        "drill_id": drill_id, "rule_id": rule, "rule_name": rule_doc["type"] if rule_doc else rule,
        "questions": [{k: q[k] for k in ("id", "sentence", "target", "choices", "error_id")} for q in questions],
    }


class AnswerIn(BaseModel):
    student: str
    drill_id: str
    question_id: str
    choice: int


@router.post("/drill/answer")
def answer(body: AnswerIn):
    drill = _drills.get(body.drill_id)
    if not drill:
        raise HTTPException(404, "모르는 drill_id (서버가 재시작됐을 수 있음 — 오답노트에서 다시 [연습하기])")
    q = next((q for q in drill["questions"] if q["id"] == body.question_id), None)
    if not q:
        raise HTTPException(404, "모르는 question_id")

    correct = body.choice == q["answer"]
    q["answered"] = correct
    rule_doc = find_rule(drill["rule_id"]) or {}
    _log({
        "ts": datetime.now().isoformat(timespec="seconds"), "student": body.student, "drill_id": body.drill_id,
        "rule_id": drill["rule_id"], "error_id": q["error_id"], "choice": q["choices"][body.choice] if 0 <= body.choice < len(q["choices"]) else None,
        "correct": correct,
    })

    done = all(x["answered"] is not None for x in drill["questions"])
    all_correct = done and all(x["answered"] for x in drill["questions"])
    streak = _update_streak(body.student, drill["rule_id"], all_correct) if done else None
    if done:
        _drills.pop(body.drill_id, None)

    return {
        "correct": correct, "answer": q["answer"], "rule_text": rule_doc.get("text", ""),
        "done": done, "all_correct": all_correct if done else None, "streak": streak,
        "overcome": (streak is not None and streak >= OVERCOME_STREAK),
    }
