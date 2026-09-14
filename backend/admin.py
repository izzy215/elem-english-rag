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

from backend import evalrun, gapcheck, golden, llm, textbook, tutor
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
        # 설명이 검색 문서(rules.jsonl)에서 나온 문장 수 — "RAG 답의 내용이 검색 문서에서 나오는가" 지표. grounded 필드는 2026-09-14 부터 기록 (없는 옛 행은 분모에서 뺌)
        "grounded": (lambda t: {"n": len(t), "yes": sum(1 for x in t if x.get("grounded"))} if t else None)(
            [r for r in rows if r.get("grounded") is not None and not r.get("ok") and r.get("rule_id") not in (None, "OTHER")]),
        # 교과서 범위 지표 (tutor 가 used_pattern·outside_words 를 로그에 쓰기 시작하면 채워짐): 교과서 표현으로 고친 문장 수 · 학년 밖 단어가 나온 문장
        "textbook": (lambda t: {"n": len(t), "used_pattern": sum(1 for x in t if x.get("used_pattern")),
                                "outside": [{"text": x.get("text"), "fixed": x.get("fixed"), "words": x.get("outside_words")} for x in t if x.get("outside_words")][:20]} if t else None)(
            [r for r in rows if "used_pattern" in r and not r.get("ok") and r.get("rule_id") not in (None, "OTHER")]),
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
        corpus = d.get("corpus") or "rules"
        corpus_kr = d.get("corpus_label") or {"rules": "규칙 설명문", "errors": "틀린 예문", "both": "예문+설명문"}.get(corpus, corpus)
        runs.append({"file": path.name, "evaluated_at": d.get("evaluated_at"), "model": model, "provider": idx.get("provider"),
                     "reranker": reranker, "corpus": corpus, "corpus_label": corpus_kr,
                     "label": model + (f" · {corpus_kr}" if corpus != "rules" else "") + (f" + 재랭킹({reranker})" if reranker else ""),
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
    corpus: str = "rules"              # 검색 대상: rules(규칙 설명문) | errors(틀린 예문) | both


@router.get("/eval_run")
def eval_run_status():
    """선택지(.env 의 모델 표) + 진행 중인 작업 상태. 끝나면 결과 파일이 data/rag_eval 에 생겨 /admin/eval_history 표에 붙는다."""
    return {"options": evalrun.options(), "job": evalrun.job_status()}


@router.post("/eval_run")
def eval_run_start(body: EvalRunIn):
    if body.backend not in ("gemini", "local", "remote"):
        raise HTTPException(400, "backend 는 gemini/local/remote 중 하나")
    if body.corpus not in ("rules", "errors", "both"):
        raise HTTPException(400, "corpus 는 rules/errors/both 중 하나")
    return evalrun.start_job(body.backend, (body.model or "").strip() or None, (body.rerank or "").strip() or None, body.topn, body.corpus)


# ── 튜터 평가 (/fix 끝까지: 검색 → LLM → 검증 → 정답 규칙과 비교) → tests/eval_fix.py 서브프로세스 ──
class FixRunIn(BaseModel):
    backend: str | None = None         # gemini | claude | LLM_ENDPOINTS 이름. 없으면 .env 의 LLM_BACKEND
    no_rag: bool = False               # True 면 검색 없이 규칙 전부를 프롬프트에 (RAG 없을 때 기준선)
    label: str = ""                    # 실행 이름 (파일명에 붙음)
    limit: int = 0                     # 앞 n 문장만 (0 = 전부)
    per_rule: int = 0                  # 규칙당 n 문장만 (0 = 전부). 화면의 "빠르게" 가 1
    normal: int = -1                   # 정상 문장 n 개만 (-1 = 전부)
    textbook: bool = True              # False 면 교과서 검색(패턴 힌트) 없이 — 교과서 범위 효과 비교용 (tutor 가 FIX_TEXTBOOK=0 을 읽을 때 유효)


@router.get("/fix_history")
def fix_history():
    """fix_compare_*.json 전부 → 실행별 규칙 정답률·정상 유지율 + 지금 시험지 최신 실행의 놓친 문장."""
    return evalrun.fix_history()


@router.get("/fix_run")
def fix_run_status():
    return {"job": evalrun.fix_job_status(), "backends": llm.backends(), "default_backend": settings.llm_backend}


@router.post("/fix_run")
def fix_run_start(body: FixRunIn):
    backend = (body.backend or settings.llm_backend or "gemini").strip()
    if backend not in llm.backends():
        raise HTTPException(400, f"모르는 백엔드: {backend} (가능: {llm.backends()})")
    return evalrun.start_fix_job(backend, body.no_rag, body.label, max(0, min(body.limit, 1000)), max(0, body.per_rule), max(-1, body.normal), body.textbook)


# ── 교과서 검색 시험 (backend/textbook.py 프로토타입 — 패턴·단어 색인에서 학생 문장과 가까운 것) ──
@router.get("/textbook")
def textbook_search(q: str = "", level: int = 3, k: int = 5, min_score: float = 0.0):
    """색인 상태 + (q 가 있으면) 검색 결과. 교수님 대응 2 의 "검색이 답에 무엇을 보태나" 를 눈으로 보는 화면용."""
    info = textbook.load_manifest()
    q = (q or "").strip()
    if not q:
        return {"index": info, "result": None}
    if not (1 <= len(q) <= 300):
        raise HTTPException(400, "문장은 1~300자")
    r = textbook.search_textbook(q, level=max(3, min(level, 6)), k_pattern=max(1, min(k, 10)), k_word=max(1, min(k, 10)), min_score=min_score)
    # 힌트를 넣을지 판정 근거 (RAG 담당이 실측으로 다듬을 임시 기준): 1위 점수 ≥ 0.85 이고 1위−5위 차이 ≥ 0.06.
    # 9/14 실측 — 교과서 문장 "I like pizza." 0.900/차이 0.107, "I go to school by bus." 0.878/0.073 · 애매한 "I like you." 0.861/0.049 · 엉뚱한 문장 0.842/0.046
    ps = [p["score"] for p in r.get("patterns", [])]
    gap = round(ps[0] - ps[min(4, len(ps) - 1)], 4) if len(ps) >= 2 else None
    top = ps[0] if ps else None
    return {"index": info, "result": r, "known_words_n": len(textbook.known_words(level)), "gap": gap, "top": top,
            "gap_threshold": 0.06, "top_threshold": 0.85, "hint": (gap is not None and gap >= 0.06 and top >= 0.85)}


def eval_sheet_hash() -> str:
    """지금 eval.csv 의 지문. 평가 파일의 evaluation_hash 와 대조해 '같은 시험지' 판정 (tests/rerank_compare.py 도 이 값을 기록)."""
    return "sha256:" + hashlib.sha256(json.dumps(golden.eval_set(), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
