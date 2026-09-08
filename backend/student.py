"""
학생 DB 읽기 — 오답노트 (PRD 4.4 · 5.2)   담당: 팀장

GET /api/notebook?student=A
  → {"active":[{rule_id, name, short, count, last, streak, examples:[{text, fixed, log_id, ts, unit}]}],
     "overcome":[{rule_id, name, count, last}],
     "stats":{"spoken": 전체 문장 수, "by_unit": {"U3": n, ...}}}

이 파일은 **읽기만** 한다. 쓰기는
  - tutor.py  /fix  → sentence_log.jsonl 한 줄, notebook.json count+1 · streak 0
  - drill.py  /drill/answer → drill_log.jsonl, notebook.json streak 갱신
가 이미 하고 있다. 파일 형식은 PRD 5.2.

chat.py(물어보기 챗)는 API 를 부르지 말고 notebook_summary(student) 를 import 해서 프롬프트 맥락으로 쓰면 된다:
  "이 학생은 과거시제 3회 (최근: 'I go to the zoo yesterday.' → 'I went to the zoo yesterday.')"
답의 근거는 여전히 rules·faq 조각이고, 이 요약은 개인화 맥락일 뿐이다.
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from backend.tutor import STUDENT_DIR, find_rule

router = APIRouter(tags=["student"])

OVERCOME_STREAK = 2      # drill.py 와 같은 값. 연속 2회 전부 정답 = 극복


# ─────────────────────────────────────────────
# 파일 읽기
# ─────────────────────────────────────────────
def _read_notebook() -> dict:
    path = STUDENT_DIR / "notebook.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_sentence_log() -> list[dict]:
    path = STUDENT_DIR / "sentence_log.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


# ─────────────────────────────────────────────
# 요약 만들기
# ─────────────────────────────────────────────
def notebook_summary(student: str, max_examples: int = 3) -> dict:
    """오답노트 화면용 + 챗봇 맥락용. notebook.json 의 규칙별 항목에 sentence_log 의 실제 문장을 붙인다."""
    book = _read_notebook().get(student, {})
    log = _read_sentence_log()
    by_log_id = {row["log_id"]: row for row in log if row.get("log_id")}

    active, overcome = [], []
    for rule_id, entry in book.items():
        rule = find_rule(rule_id) or {}
        # 최근 것부터: log_ids 는 오래된 → 최신 순으로 쌓이므로 뒤집는다
        examples = []
        for log_id in reversed(entry.get("log_ids", [])):
            row = by_log_id.get(log_id)
            if row:
                examples.append({"text": row.get("text", ""), "fixed": row.get("fixed", ""), "log_id": log_id,
                                 "ts": row.get("ts", ""), "unit": row.get("unit", "")})
            if len(examples) >= max_examples:
                break
        item = {
            "rule_id": rule_id,
            "name": rule.get("type", rule_id),
            "short": rule.get("short", ""),
            "count": entry.get("count", 0),
            "last": entry.get("last", ""),
            "streak": entry.get("streak", 0),
            "examples": examples,
        }
        if item["streak"] >= OVERCOME_STREAK:
            overcome.append(item)
        else:
            active.append(item)

    active.sort(key=lambda x: x["count"], reverse=True)   # 많이 틀린 규칙부터 (PRD 7 우선 출제)
    overcome.sort(key=lambda x: x["last"], reverse=True)

    mine = [row for row in log if row.get("student") == student]
    by_unit: dict[str, int] = {}
    for row in mine:
        unit = row.get("unit") or "?"
        by_unit[unit] = by_unit.get(unit, 0) + 1

    return {"active": active, "overcome": overcome, "stats": {"spoken": len(mine), "by_unit": by_unit}}


def notebook_text(student: str) -> str:
    """챗봇 프롬프트에 그대로 넣을 수 있는 한국어 요약 (chat.py 용)."""
    s = notebook_summary(student, max_examples=1)
    if not s["active"] and not s["overcome"]:
        return "아직 오답노트가 비어 있음."
    lines = []
    for it in s["active"]:
        ex = it["examples"][0] if it["examples"] else None
        line = f"- {it['name']}({it['rule_id']}) {it['count']}회"
        if ex:
            line += f" · 최근: '{ex['text']}' → '{ex['fixed']}'"
        lines.append(line)
    if s["overcome"]:
        lines.append("- 극복한 규칙: " + ", ".join(it["name"] for it in s["overcome"]))
    return "\n".join(lines)


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
@router.get("/notebook")
def api_notebook(student: str = "A"):
    return notebook_summary(student)
