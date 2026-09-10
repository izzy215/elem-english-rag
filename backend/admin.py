"""
관리자 화면 집계 — 담당: 팀장   (PRD 3.7 관리자 · 4.4 GET /admin/log)

GET /admin/golden        골든 데이터 파일별 개수 + 색인 상태 (rules.jsonl 개수와 색인 개수가 다르면 index_stale)
GET /admin/log?days=7    학생 문장 로그(data/student/sentence_log.jsonl) → 규칙별 걸린 횟수 · 학생 수 · 예시 문장,
                         모델별 처리 건수(llm), 우리 규칙으로 못 짚은 문장(gaps: 규칙 밖 + 진단 실패, 최근 30개)

읽기만 한다. 골든·색인·학생 파일에 아무것도 쓰지 않는다 (로그를 읽을 때만 tutor 의 쓰기 자물쇠를 잠깐 잡는다).
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter

from backend import golden, tutor

router = APIRouter(prefix="/admin", tags=["admin"])

# (파일, 화면 설명, 검색 색인에 들어가는지)
FILES = [
    ("rules.jsonl", "문법 규칙 설명 조각 — RAG 검색 대상 (교재)", True),
    ("faq.jsonl", "더 물어보기 FAQ — 챗봇 답변 근거", False),
    ("units.csv", "유닛 · 미션 · 힌트 단어 · 유닛별 규칙 id", False),
    ("words.csv", "단어 · 뜻 · 예문", False),
    ("patterns.csv", "문장 패턴 · 뜻 · 규칙 id", False),
    ("errors.jsonl", "오류 문장 예시 — 연습 문제·평가용", False),
    ("eval.csv", "시험지: 문장 → 정답 규칙", False),
]


def _count(path) -> int | None:
    """csv 는 헤더 뺀 행 수, jsonl 은 빈 줄 뺀 줄 수. 파일이 없으면 None."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig") as f:
        if path.suffix == ".csv":
            return max(sum(1 for _ in csv.reader(f)) - 1, 0)
        return sum(1 for line in f if line.strip())


@router.get("/golden")
def golden_status():
    d = golden.SAMPLE if golden.using_sample() else golden.GOLDEN
    files = [{"file": n, "desc": desc, "indexed": idx, "count": _count(d / n)} for n, desc, idx in FILES]
    index = None
    try:                                                   # 색인 manifest (RAG 담당 indexing.py). 없거나 깨져도 화면은 살린다
        from backend import indexing
        m = indexing.load_manifest() or {}
        if m.get("count") is not None:
            index = {"count": m.get("count"), "model": m.get("model"), "generated_at": m.get("generated_at")}
    except Exception:
        index = None
    rules_n = next((f["count"] for f in files if f["file"] == "rules.jsonl"), None)
    return {
        "dir": str(d.relative_to(golden.ROOT)).replace("\\", "/"),
        "using_sample": golden.using_sample(),
        "files": files,
        "index": index,
        "index_stale": bool(index and rules_n is not None and index["count"] != rules_n),
    }


@router.get("/log")
def sentence_log(days: int = 7):
    """최근 days 일의 학생 문장 로그를 규칙별로 묶는다. ok=true(맞은 문장) 는 개수에만 들어가고 규칙 표에는 안 나온다."""
    path = tutor.STUDENT_DIR / "sentence_log.jsonl"
    since = datetime.now() - timedelta(days=days)
    rows: list[dict] = []
    if path.exists():
        with tutor._lock, path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    ts = datetime.fromisoformat(r.get("ts", ""))
                except ValueError:
                    continue
                if ts >= since:
                    rows.append(r)
    by: dict[str, dict] = {}
    for r in rows:
        rid = r.get("rule_id")
        if not rid or r.get("ok"):
            continue
        g = by.setdefault(rid, {"rule_id": rid, "name": (golden.find_rule(rid) or {}).get("type", rid),
                                "count": 0, "students": set(), "example": ""})
        g["count"] += 1
        g["students"].add(r.get("student"))
        g["example"] = r.get("text") or g["example"]        # 가장 최근 문장이 예시
    out = sorted(({**g, "students": len(g["students"])} for g in by.values()), key=lambda g: -g["count"])
    return {
        "days": days,
        "n": len(rows),
        "ok_n": sum(1 for r in rows if r.get("ok")),
        "students": len({r.get("student") for r in rows}),
        "llm": dict(Counter(r.get("llm") or "?" for r in rows)),   # 어느 모델이 몇 문장 처리했나 (발표용)
        "rows": out,
        # 우리 규칙으로 못 짚은 문장 — 규칙 밖(OTHER) 으로 고친 것 + 검증 실패로 502 난 것. 데이터팀 '빠진 규칙' 안건 (최근 것부터 30개)
        "gaps": [{"ts": r.get("ts"), "text": r.get("text"), "fixed": r.get("fixed"), "kind": "규칙 밖" if r.get("rule_id") == "OTHER" else "진단 실패",
                  "reason": r.get("failed") or ""}
                 for r in reversed(rows) if r.get("rule_id") == "OTHER" or r.get("failed")][:30],
    }
