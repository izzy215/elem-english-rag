"""
골든 데이터셋 읽기 + 학습 데이터 API (Plan B)   담당: TTS 팀원

data/golden/ 에 진짜 파일(words.csv 등)이 있으면 그것을, 없으면 data/golden/_sample-B/ 의
임시 데이터를 읽는다. 이 파일은 TTS 팀원 소유. 다른 사람은 여기 함수를 import 해서 쓰기만 한다.

데이터 출처는 Plan B 형식(patterns.csv 등) 하나뿐이지만, /api/sentences 는 그 데이터를
Plan A 화면(learn.html)이 기대하는 옛 모양으로 바꿔서 같이 내보낸다 — learn.html 을 고치지
않고도 계속 쓸 수 있게 하려는 목적. 새 화면은 /api/patterns 를 쓰면 된다.

파일 6개 (docs/plan-B/data-pipeline-plan.md, _sample-B/README.md 참고):
  units.csv    level·unit·title·mission·hint_words·rule_ids
  words.csv    id·level·unit·word·meaning·example
  patterns.csv id·level·unit·text·meaning·tip·rule_id
  rules.jsonl  id·type·unit·text·short·examples·wrong_example   (RAG 검색 대상)
  errors.jsonl id·unit·rule_id·error·correct·target·fix·distractors
  faq.jsonl    id·unit·question·variants·answer·rule_ids·example (RAG 검색 대상)
  eval.csv     text·expected_rule_id·note
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
        # sentences: Plan A 화면(learn.html/units.html)이 이 키를 읽어서, patterns 개수를 그대로 별칭으로 얹어둠
        "sentences": sum(1 for p in patterns_ if int(p["level"]) == level and p["unit"] == u["unit"]),
    } for u in rows]


def words(level: int, unit: str) -> list[dict]:
    return [{"id": w["id"], "word": w["word"], "meaning": w["meaning"], "example": w["example"],
             "source_page": int(w.get("source_page") or 0)}  # Plan B words.csv 엔 없는 컬럼 → 없으면 0
            for w in _read("words.csv") if int(w["level"]) == level and w["unit"] == unit]


def patterns(level: int, unit: str) -> list[dict]:
    return [{"id": p["id"], "text": p["text"], "meaning": p["meaning"], "tip": p["tip"], "rule_id": p["rule_id"]}
            for p in _read("patterns.csv") if int(p["level"]) == level and p["unit"] == unit]


def sentences(level: int, unit: str) -> list[dict]:
    """Plan A 화면(learn.html) 호환용 — patterns.csv 를 "문장" 모양으로 바꿔서 내보낸다.
    데이터 출처는 patterns()와 동일(patterns.csv), 응답 형태만 옛 sentences 계약에 맞춘다."""
    return [{"id": p["id"], "sentence": p["text"], "meaning": p["meaning"], "source_page": 0}
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


def errors() -> list[dict]:
    """전체 오류 예시 (규칙 연습·평가·데모용)."""
    return _read_jsonl("errors.jsonl")


def find_error(error_id: str) -> dict | None:
    for e in errors():
        if e["id"] == error_id:
            return e
    return None


def eval_set() -> list[dict]:
    """RAG 정확도 평가셋 (문장 → 정답 규칙 id). 이름은 eval_set — eval 은 파이썬 내장 함수라 피함."""
    return _read("eval.csv")


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


@router.get("/sentences")
def api_sentences(level: int, unit: str):
    """Plan A 화면(learn.html) 호환용. patterns()와 같은 데이터를 다른 모양으로 줌."""
    return sentences(level, unit)


@router.get("/progress")
def api_progress(student: str, level: int, unit: str):
    """TODO: data/student/progress.json · wrong_words.json 에서 읽기 (quiz.py 가 기록한 것)"""
    return {"learned": 0, "total": len(words(level, unit)), "quiz_taken": 0, "wrong_words": []}
