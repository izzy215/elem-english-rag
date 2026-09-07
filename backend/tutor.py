"""
튜터 — 내 문장 고쳐주기 (PRD 4.3)   담당: 팀장

POST /api/fix  {student, level, unit, text, source}
  → {ok, rule, runner_up, wrong, fix, fixed, why, source, more_errors, suggested_questions, mission, log_id, mode}

동작 (지금은 "fallback" 모드 하나):
  1. 규칙 조각 전부(rules.jsonl)와 오늘의 미션(units.csv)을 프롬프트(prompts/fix_fallback.txt)에 넣는다
  2. Gemini 에 JSON 으로만 답하게 해서 받는다
  3. 규칙 조각을 근거(source)로 붙이고, 학생 DB 에 문장 로그 + 오답노트를 기록한다

RAG 담당의 /rag/search 가 완성되면 _search_rule() 을 채워 "rag" 모드(1위 조각만 넣기)로 바꾼다.
화면(frontend/js/tutor.js)은 이 응답 형식을 이미 기다리고 있다. 필드 이름을 바꾸면 화면도 같이 바꿔야 한다.

데이터 위치: data/golden/rules.jsonl · units.csv 가 있으면 그것, 없으면 data/golden/_sample-B/ 의 샘플.
학생 DB: data/student/sentence_log.jsonl, notebook.json (PRD 5.2 형식, gitignore)
"""
from __future__ import annotations

import csv
import json
import re
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.config import settings

ROOT = Path(__file__).resolve().parent.parent          # project/
GOLDEN = ROOT / "data" / "golden"
SAMPLE_B = GOLDEN / "_sample-B"
STUDENT_DIR = ROOT / "data" / "student"
PROMPT_FILE = Path(__file__).parent / "prompts" / "fix_fallback.txt"

router = APIRouter(tags=["tutor"])
_lock = threading.Lock()
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


# ─────────────────────────────────────────────
# 데이터 읽기 (골든 → 없으면 샘플 B)
# ─────────────────────────────────────────────
def _golden_path(name: str) -> Path:
    return GOLDEN / name if (GOLDEN / name).exists() else SAMPLE_B / name


def rules() -> list[dict]:
    path = _golden_path("rules.jsonl")
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def find_rule(rule_id: str | None) -> dict | None:
    return next((r for r in rules() if r["id"] == rule_id), None) if rule_id else None


def unit_info(level: int, unit: str) -> dict:
    path = _golden_path("units.csv")
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("level")) == str(level) and row.get("unit") == unit:
                return row
    return {}


# ─────────────────────────────────────────────
# 프롬프트 · Gemini
# ─────────────────────────────────────────────
def _render(template: str, **vars_: str) -> str:
    for k, v in vars_.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def _rules_block(rule_list: list[dict]) -> str:
    return "\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in rule_list)


def _ask_gemini(prompt: str) -> dict:
    """JSON 만 받는다. 모델이 코드펜스를 붙여도 벗겨서 파싱."""
    resp = _get_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def _search_rule(text: str) -> dict | None:
    """TODO(RAG 담당 완성 후): rag.search(text, kind="rule") 1위가 threshold 이상이면 그 조각을 돌려준다.
    지금은 None → 폴백(전체 규칙) 모드."""
    return None


# ─────────────────────────────────────────────
# 학생 DB (PRD 5.2)
# ─────────────────────────────────────────────
def _log_sentence(row: dict) -> None:
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, (STUDENT_DIR / "sentence_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _notebook_add(student: str, rule_id: str, log_id: str) -> None:
    """notebook.json  {"A":{"R-01":{"count":3,"last":"2026-09-10","streak":0,"log_ids":[...]}}}"""
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    path = STUDENT_DIR / "notebook.json"
    with _lock:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = data.setdefault(student, {}).setdefault(rule_id, {"count": 0, "last": "", "streak": 0, "log_ids": []})
        entry["count"] += 1
        entry["last"] = datetime.now().strftime("%Y-%m-%d")
        entry["streak"] = 0                       # 또 틀렸으니 극복 진행 초기화
        entry["log_ids"] = (entry["log_ids"] + [log_id])[-10:]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
class FixIn(BaseModel):
    student: str = "A"
    level: int = 2
    unit: str = ""
    text: str
    source: str = "typed"           # "stt" | "typed"


@router.post("/fix")
def fix(body: FixIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "text 가 비어 있음")
    if not settings.has_api_key:
        raise HTTPException(500, "GEMINI_API_KEY 가 설정되어 있지 않음")

    all_rules = rules()
    if not all_rules:
        raise HTTPException(500, "rules.jsonl 이 없음 (data/golden/ 또는 _sample-B/)")
    unit = unit_info(body.level, body.unit)

    # 모드: RAG 검색이 되면 1위 조각만, 아니면 전체 규칙 (지금은 항상 fallback)
    hit = _search_rule(text)
    candidates = [hit] if hit else all_rules
    mode = "rag" if hit else "fallback"

    prompt = _render(
        PROMPT_FILE.read_text(encoding="utf-8"),
        mission=unit.get("mission") or "(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words=", ".join((unit.get("hint_words") or "").split(";")) or "(없음)",
        all_rules=_rules_block(candidates),
        sentence=text,
    )
    try:
        out = _ask_gemini(prompt)
    except json.JSONDecodeError:
        raise HTTPException(502, "Gemini 응답을 JSON 으로 읽지 못함")
    except Exception as e:                                   # 할당량·네트워크 등
        raise HTTPException(502, f"Gemini 호출 실패: {e}")

    rule = find_rule(out.get("rule_id")) if not out.get("ok") else None
    ok = bool(out.get("ok")) or rule is None                 # 목록에 없는 id 를 지어내면 ok 로 취급 (근거 없는 지적 금지)
    fixed = (out.get("fixed") or text).strip()
    log_id = "L-" + datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    mission = out.get("mission") if isinstance(out.get("mission"), dict) else {"ok": True, "nudge": ""}

    result = {
        "ok": ok,
        "rule": {"id": rule["id"], "name": rule["type"], "score": None} if rule else None,
        "runner_up": None,
        "wrong": None if ok else out.get("wrong"),
        "fix": None if ok else out.get("fix"),
        "fixed": text if ok else fixed,
        "why": out.get("why") or ("문법에 맞는 문장이에요. 다른 문장도 말해볼까요?" if ok else ""),
        "source": {"chunk_id": rule["id"], "text": rule["text"]} if rule else None,
        "more_errors": bool(out.get("more_errors")) and not ok,
        "suggested_questions": [q for q in (out.get("suggested_questions") or []) if isinstance(q, str)][:2] + ["다른 예문 보여줘"],
        "mission": {"ok": bool(mission.get("ok", True)), "nudge": mission.get("nudge") or ""},
        "log_id": log_id,
        "mode": mode,
    }

    _log_sentence({
        "log_id": log_id, "ts": datetime.now().isoformat(timespec="seconds"), "student": body.student,
        "level": body.level, "unit": body.unit, "text": text, "source": body.source,
        "rule_id": rule["id"] if rule else None, "ok": ok, "fixed": result["fixed"],
        "mission_ok": result["mission"]["ok"], "mode": mode,
    })
    if rule:
        _notebook_add(body.student, rule["id"], log_id)
    return result
