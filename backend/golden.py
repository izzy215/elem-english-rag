"""
골든 데이터셋 읽기 + 학습 데이터 API (PRD 5.1 · 6.1)   담당: TTS 팀원

data/golden/ 에 진짜 파일(words.csv 등)이 있으면 그것을, 없으면 data/golden/_sample/ 의 임시 데이터를 읽는다.
이 파일은 TTS 팀원 소유. 다른 사람은 여기 함수를 import 해서 쓰기만 한다.

※ 임시로 _sample으로 되돌린 상태 — 실제 프론트(learn.html)로 파형분석을
눈으로 확인하려는 목적. Plan B 형식(_sample-B: patterns.csv·rules.jsonl 등)은 추후 수정 예정.
"""
from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data" / "golden"
SAMPLE = GOLDEN / "_sample"

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
    sents = _read("sentences.csv")
    rows = [u for u in _read("units.csv") if int(u["level"]) == level]
    rows.sort(key=lambda u: int(u.get("order", 0)))
    return [{
        "unit": u["unit"], "title": u["title"],
        "words": sum(1 for w in words_ if int(w["level"]) == level and w["unit"] == u["unit"]),
        "sentences": sum(1 for s in sents if int(s["level"]) == level and s["unit"] == u["unit"]),
    } for u in rows]


def words(level: int, unit: str) -> list[dict]:
    return [{"id": w["id"], "word": w["word"], "meaning": w["meaning"], "example": w["example"],
             "source_page": int(w["source_page"] or 0)}
            for w in _read("words.csv") if int(w["level"]) == level and w["unit"] == unit]


def sentences(level: int, unit: str) -> list[dict]:
    return [{"id": s["id"], "sentence": s["sentence"], "meaning": s["meaning"],
             "source_page": int(s["source_page"] or 0)}
            for s in _read("sentences.csv") if int(s["level"]) == level and s["unit"] == unit]


def find_item(item_id: str) -> dict | None:
    """TTS 용: 단어/문장 id → 원문 텍스트"""
    for w in _read("words.csv"):
        if w["id"] == item_id:
            return {"id": item_id, "text": w["word"], "kind": "word"}
    for s in _read("sentences.csv"):
        if s["id"] == item_id:
            return {"id": item_id, "text": s["sentence"], "kind": "sentence"}
    return None


# ─────────────────────────────────────────────
# API (PRD 5.1)
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


@router.get("/sentences")
def api_sentences(level: int, unit: str):
    return sentences(level, unit)


@router.get("/progress")
def api_progress(student: str, level: int, unit: str):
    """TODO: data/student/progress.json · wrong_words.json 에서 읽기 (quiz.py 가 기록한 것)"""
    return {"learned": 0, "total": len(words(level, unit)), "quiz_taken": 0, "wrong_words": []}

