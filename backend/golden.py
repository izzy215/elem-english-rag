"""
골든 데이터셋 읽기 + 학습 데이터 API (PRD 5.1 · 6.1)   담당: TTS 팀원

data/golden/ 에 진짜 파일(words.csv 등)이 있으면 그것을, 없으면 data/golden/_sample/ 의 임시 데이터를 읽는다.
이 파일은 TTS 팀원 소유. 다른 사람은 여기 함수를 import 해서 쓰기만 한다.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data" / "golden"
SAMPLE = GOLDEN / "_sample-B"

router = APIRouter(tags=["golden"])


# ─────────────────────────────────────────────
# 파일 읽기
# ─────────────────────────────────────────────
def _dir() -> Path:
    return GOLDEN if (GOLDEN / "words.csv").exists() else SAMPLE


def _read(name: str) -> list[dict]:
    path = _dir() / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(name: str) -> list[dict]:
    path = _dir() / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _split(value: str) -> list[str]:
    return [v for v in (value or "").split(";") if v]


def using_sample() -> bool:
    return _dir() == SAMPLE


def golden_files() -> list[str]:
    return sorted(p.name for p in _dir().glob("*.csv")) + sorted(p.name for p in _dir().glob("*.jsonl"))


LEVEL_LABELS = {1: "Level 1 · 3~4학년", 2: "Level 2 · 5학년", 3: "Level 3 · 6학년"}


def levels() -> list[dict]:
    units_ = _read("units.csv")
    out = []
    for lv in sorted({int(u["level"]) for u in units_} | set(LEVEL_LABELS)):
        n = sum(1 for u in units_ if int(u["level"]) == lv)
        out.append({"level": lv, "label": LEVEL_LABELS.get(lv, f"Level {lv}"), "units": n})
    return out


def units(level: int) -> list[dict]:
    words_ = _read("words.csv")
    patterns_ = _read("patterns.csv")
    rows = [u for u in _read("units.csv") if int(u["level"]) == level]
    return [{
        "unit": u["unit"], "title": u["title"], "mission": u.get("mission", ""),
        "hint_words": _split(u.get("hint_words", "")), "rule_ids": _split(u.get("rule_ids", "")),
        "words": sum(1 for w in words_ if int(w["level"]) == level and w["unit"] == u["unit"]),
        "patterns": sum(1 for p in patterns_ if int(p["level"]) == level and p["unit"] == u["unit"]),
    } for u in rows]


def words(level: int, unit: str) -> list[dict]:
    return [{"id": w["id"], "word": w["word"], "meaning": w["meaning"], "example": w["example"]}
            for w in _read("words.csv") if int(w["level"]) == level and w["unit"] == unit]


def patterns(level: int, unit: str) -> list[dict]:
    return [{"id": p["id"], "text": p["text"], "meaning": p["meaning"], "tip": p["tip"], "rule_id": p["rule_id"]}
            for p in _read("patterns.csv") if int(p["level"]) == level and p["unit"] == unit]


def find_item(item_id: str) -> dict | None:
    """TTS 용: 단어/패턴 id → 원문 텍스트"""
    for w in _read("words.csv"):
        if w["id"] == item_id:
            return {"id": item_id, "text": w["word"], "kind": "word"}
    for p in _read("patterns.csv"):
        if p["id"] == item_id:
            return {"id": item_id, "text": p["text"], "kind": "pattern"}
    return None


def rules() -> list[dict]:
    """전체 문법 규칙 조각 (RAG 인덱싱용)."""
    return _read_jsonl("rules.jsonl")


def find_rule(rule_id: str) -> dict | None:
    """규칙 id → 규칙 조각 (챗봇 scope=rule, 오답 설명 등에서 조회용)"""
    for r in rules():
        if r["id"] == rule_id:
            return r
    return None


def faqs() -> list[dict]:
    """전체 FAQ 조각 (물어보기 챗 RAG 인덱싱용)."""
    return _read_jsonl("faq.jsonl")


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
@router.get("/levels")
def api_levels():
    return levels()


@router.get("/units")
def api_units(level: int):
    return units(level)


@router.get("/words")
def api_words(level: int, unit: str):
    return words(level, unit)


@router.get("/patterns")
def api_patterns(level: int, unit: str):
    return patterns(level, unit)


@router.get("/progress")
def api_progress(student: str, level: int, unit: str):
    """TODO: data/student/progress.json · wrong_words.json 에서 읽기 (quiz.py 가 기록한 것)"""
    return {"learned": 0, "total": len(words(level, unit)), "quiz_taken": 0, "wrong_words": []}
