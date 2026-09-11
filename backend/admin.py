"""
관리자 화면 집계 — 담당: 팀장   (PRD 3.7 관리자 · 4.4 GET /admin/log)

GET /admin/golden        골든 데이터 파일별 개수 + 색인 상태 (rules.jsonl 개수와 색인 개수가 다르면 index_stale)
GET /admin/log?days=7    학생 문장 로그(data/student/sentence_log.jsonl) → 규칙별 걸린 횟수 · 학생 수 · 예시 문장,
                         모델별 처리 건수(llm), 우리 규칙으로 못 짚은 문장(gaps: 규칙 밖 + 진단 실패 최근 30개 + tests/gen_gaps.py 생성 점검 후보)

읽기만 한다. 골든·색인·학생 파일에 아무것도 쓰지 않는다 (로그를 읽을 때만 tutor 의 쓰기 자물쇠를 잠깐 잡는다).
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from backend import evalrun, gapcheck, golden, llm, tutor
from backend.config import settings

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
    gaps = [{"ts": r.get("ts"), "text": r.get("text"), "fixed": r.get("fixed"), "kind": "규칙 밖" if r.get("rule_id") == "OTHER" else "진단 실패",
             "reason": r.get("failed") or "", "llm": r.get("llm") or "?", "student": r.get("student")}
            for r in reversed(rows) if r.get("rule_id") == "OTHER" or r.get("failed")][:30]
    g = gapcheck.latest()                                    # 생성 점검(backend/gapcheck.py) 결과: 규칙 밖 오류로 만들었는데 /fix 가 맞다고 한 문장 (모델이 붙인 오류 이름)
    if g:
        gaps += [{"ts": g.get("ran_at"), "text": m.get("text"), "fixed": m.get("correct") or None, "kind": "생성 점검",
                  "reason": f"{m.get('intended', '')} (모델 표시, 확인 필요)", "llm": f"{g.get('backend')}:{g.get('model') or ''}", "student": g.get("student")}
                 for m in g.get("missed_outside", [])][:30]
    return {
        "days": days,
        "n": len(rows),
        "ok_n": sum(1 for r in rows if r.get("ok")),
        "students": len({r.get("student") for r in rows}),
        "llm": dict(Counter(r.get("llm") or "?" for r in rows)),   # 어느 모델이 몇 문장 처리했나 (발표용)
        "rows": out,
        # 처리 시간 (ms 평균): 전체 · 검색 · 모델 호출 수 — total_ms 가 있는 행만 (성공한 문장). 시연 때 "몇 초 걸리나" 답용
        "timing": (lambda t: {"n": len(t), "total_ms": int(sum(x.get("total_ms") or 0 for x in t) / len(t)),
                              "search_ms": int(sum(x.get("search_ms") or 0 for x in t) / len(t)),
                              "llm_calls": round(sum(x.get("llm_calls") or 0 for x in t) / len(t), 1)} if t else None)(
            [r for r in rows if r.get("total_ms")]),
        # 우리 규칙으로 못 짚은 문장 — 학생 로그의 규칙 밖(OTHER)·진단 실패(502) 최근 30개 + 생성 점검(tests/gen_gaps.py) 후보. 데이터팀 '빠진 규칙' 안건
        "gaps": gaps,
    }


# ── 생성 점검 (backend/gapcheck.py) — 관리자 화면 버튼 ──
class GenIn(BaseModel):
    n: int = 20
    backend: str | None = None       # gemini | claude | LLM_ENDPOINTS 이름. 없으면 .env 의 LLM_BACKEND


@router.get("/gen_gaps")
def gen_gaps_latest():
    """최근 생성 점검 결과(어떤 모델로 어떤 문장을 넣었고 튜터가 뭐라 했나) + 지금 도는 작업 상태 + 고를 수 있는 백엔드."""
    g = gapcheck.latest() or {}
    return {"latest": g, "job": gapcheck.job_status(), "backends": llm.backends(), "default_backend": settings.llm_backend}


@router.post("/gen_gaps")
def gen_gaps_run(body: GenIn):
    """생성 점검을 백그라운드로 시작한다 (한 번에 하나). 진행은 GET /admin/gen_gaps 의 job 으로 본다."""
    if body.backend and body.backend not in llm.backends():
        raise HTTPException(400, f"모르는 백엔드: {body.backend} (가능: {llm.backends()})")
    return gapcheck.start_job(n=max(1, min(body.n, 60)), backend=body.backend)


# ── 검색 평가 이력 (data/rag_eval/retrieval_eval_<시각>.json 전부) — 임베딩 모델·재랭킹별 비교 막대용 ──
@router.get("/eval_history")
def eval_history():
    """tests/eval_rag.py 가 남긴 평가 파일을 전부 읽어 실행별 결과와 '모델(+재랭커)별 최신' 목록을 준다.
    파일에 reranker 정보가 있으면(index.reranker 또는 최상위 reranker) 라벨에 ' + 재랭킹' 을 붙인다 — RAG 담당이 재랭킹을 평가에 넣으면 자동 반영.
    비교는 같은 시험지끼리만 뜻이 있어서, 지금 eval.csv 와 짝이 맞는 실행(문장 수 같고, 해시가 있으면 해시도 같음)만 latest 에 넣고
    나머지(옛 시험지 65문장, --step 으로 일부만 돌린 실험 등)는 runs 에 same_sheet=False 로만 남긴다 — 화면 표에는 안 나옴."""
    out_dir = golden.ROOT / "data" / "rag_eval"
    eval_n, eval_hash = len(golden.eval_set()), eval_sheet_hash()
    runs = []
    for path in sorted(out_dir.glob("retrieval_eval_2*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        idx = d.get("index") or {}
        reranker = d.get("reranker") or idx.get("reranker")
        model = idx.get("model") or "?"
        runs.append({"file": path.name, "evaluated_at": d.get("evaluated_at"), "model": model, "provider": idx.get("provider"),
                     "reranker": reranker, "label": model + (f" + 재랭킹({reranker})" if reranker else ""),
                     "n": d.get("n"), "total_n": d.get("total_n"), "k": d.get("k"),
                     "hit_at_1": d.get("hit_at_1"), "hit_at_3": d.get("hit_at_3"), "hit_at_5": d.get("hit_at_5"),
                     "search_failures": d.get("search_failures"), "data_hash": d.get("data_hash"),
                     "same_sheet": (d.get("total_n") or d.get("n")) == eval_n and (d.get("evaluation_hash") or eval_hash) == eval_hash})
    latest: dict[str, dict] = {}
    for r in runs:                                           # 라벨별 가장 최근 실행 (파일명이 시각순) — 지금 시험지와 짝이 맞는 것만
        if r["same_sheet"]:
            latest[r["label"]] = r
    hidden = len({r["label"] for r in runs if not r["same_sheet"]})
    return {"runs": runs, "latest": sorted(latest.values(), key=lambda r: -(r["hit_at_3"] or 0)),
            "sheet": {"n": eval_n, "hash": eval_hash, "hidden_labels": hidden}}


# ── 검색 평가 실행 (임베딩 모델·재랭킹 선택 → tests/eval_embed.py 서브프로세스, backend/evalrun.py) ──
class EvalRunIn(BaseModel):
    backend: str = "gemini"            # gemini | local | remote
    model: str | None = None           # local/remote 모델 이름 (.env 표에서 고름)
    rerank: str | None = None          # 재랭커 이름. 없으면 검색만
    topn: int = 10                     # 재랭킹에 넣을 검색 상위 개수


@router.get("/eval_run")
def eval_run_status():
    """선택지(.env 의 모델 표) + 진행 중인 작업 상태. 끝나면 결과 파일이 data/rag_eval 에 생겨 /admin/eval_history 표에 붙는다."""
    return {"options": evalrun.options(), "job": evalrun.job_status()}


@router.post("/eval_run")
def eval_run_start(body: EvalRunIn):
    if body.backend not in ("gemini", "local", "remote"):
        raise HTTPException(400, "backend 는 gemini/local/remote 중 하나")
    return evalrun.start_job(body.backend, (body.model or "").strip() or None, (body.rerank or "").strip() or None, body.topn)


def eval_sheet_hash() -> str:
    """지금 eval.csv 의 지문. 평가 파일의 evaluation_hash 와 대조해 '같은 시험지' 판정 (tests/rerank_compare.py 도 이 값을 기록)."""
    return "sha256:" + hashlib.sha256(json.dumps(golden.eval_set(), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
