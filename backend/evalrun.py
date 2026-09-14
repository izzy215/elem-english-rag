"""
관리자 화면의 평가 실행 버튼 두 개 — 둘 다 tests/ 의 스크립트를 백그라운드 서브프로세스로 돌리고 진행률을 폴링한다.
(팀장 · 2026-09-11. 생성 점검(gapcheck.py)과 같은 "시작 → 진행률 폴링" 방식)

  ① 검색 평가  [검색 평가 실행]  → tests/eval_embed.py   임베딩 모델(+재랭킹)별 hit@1/3/5. 결과 retrieval_eval_*.json → /admin/eval_history
  ② 튜터 평가  [튜터 평가 실행]  → tests/eval_fix.py     /fix 끝까지(검색 → LLM → 검증) 돌려 규칙 정답률·정상 유지율. 결과 fix_compare_*.json → /admin/fix_history

서브프로세스인 이유: backend/embedding.py 가 import 시점에 .env 의 모델을 고정해서, 서버 프로세스 안에서는 다른 모델을
못 쓴다. 별도 프로세스에 환경변수만 덮어써서 돌리면 .env 도, 서비스가 쓰는 data/chroma 색인도 그대로다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from backend import golden

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "rag_eval"

_DEFAULT_MODELS = ["intfloat/multilingual-e5-base", "all-MiniLM-L6-v2", "intfloat/multilingual-e5-large",
                   "all-mpnet-base-v2", "BAAI/bge-m3", "paraphrase-multilingual-mpnet-base-v2", "paraphrase-multilingual-MiniLM-L12-v2"]
RERANKERS = ["BAAI/bge-reranker-v2-m3", "BAAI/bge-reranker-base", "cross-encoder/ms-marco-MiniLM-L-6-v2"]
_MODEL_LINE = re.compile(r"^#+\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+|all-[A-Za-z0-9_.\-]+|paraphrase-[A-Za-z0-9_.\-]+)\s+\d+(\.\d+)?%")
_PROGRESS = re.compile(r"\[\s*(\d+)/\s*(\d+)\]")
_SAVED = re.compile(r"(retrieval_eval_\S+\.json|fix_compare_\S+\.json)")

_lock = threading.Lock()


def _new_job() -> dict:
    return {"running": False, "started": None, "done": 0, "total": 0, "label": None, "error": None, "log": [], "result_file": None}


_jobs: dict[str, dict] = {"embed": _new_job(), "fix": _new_job()}


# ── 공통: 서브프로세스 실행 + 진행률 ────────────────────────────────────────
def _status(kind: str) -> dict:
    with _lock:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _jobs[kind].items()}


def _start(kind: str, label: str, cmd: list[str]) -> dict:
    with _lock:
        if _jobs[kind]["running"]:
            return _status(kind)
        _jobs[kind].update(running=True, started=datetime.now().isoformat(timespec="seconds"), done=0, total=0, label=label, error=None, log=[], result_file=None)
    job = _jobs[kind]

    def run() -> None:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LOG_PROMPT": "0"}   # 프롬프트 전문 출력은 끔 (로그가 수천 줄이 됨)
        try:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()
                if not line or "Warning" in line or "Loading weights" in line or line.startswith("[fix]") or line.startswith("[llm]"):
                    continue                                   # 튜터 내부 로그([fix]/[llm])는 진행률에 안 씀
                m = _PROGRESS.search(line)
                with _lock:
                    if m:
                        job["done"], job["total"] = int(m.group(1)), int(m.group(2))
                    m2 = _SAVED.search(line)
                    if m2 and ("저장" in line or "saved" in line.lower()):
                        job["result_file"] = Path(m2.group(1)).name
                    job["log"].append(line[:200])
                    if len(job["log"]) > 400:
                        del job["log"][:-300]
            code = proc.wait()
            with _lock:
                if code != 0 and not job["error"]:
                    job["error"] = f"종료 코드 {code}: {' / '.join(job['log'][-3:])[:300]}"
        except Exception as e:  # noqa: BLE001
            with _lock:
                job["error"] = f"{type(e).__name__}: {e}"
        finally:
            with _lock:
                job["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return _status(kind)


# ── ① 검색 평가 ────────────────────────────────────────────────────────────
def _env_models() -> list[str]:
    """`.env`(없으면 .env.example)의 모델 표(### 모델이름  xx%)에서 이름을 읽는다. 표가 없으면 기본 목록."""
    for name in (".env", ".env.example"):
        p = ROOT / name
        if not p.exists():
            continue
        found = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _MODEL_LINE.match(line.strip())
            if m and m.group(1) not in found:
                found.append(m.group(1))
        if found:
            return found
    return list(_DEFAULT_MODELS)


def options() -> dict:
    """검색 평가 선택지. 지금 .env 가 가리키는 백엔드·모델을 default 로 표시."""
    backend = os.environ.get("EMBEDDING_BACKEND", "gemini").strip().lower()
    model = {"gemini": "gemini-embedding-001", "local": os.environ.get("EMBEDDING_LOCAL_MODEL", "intfloat/multilingual-e5-base"),
             "remote": os.environ.get("EMBEDDING_REMOTE_MODEL", "intfloat/multilingual-e5-base")}.get(backend, "?")
    return {"backends": ["gemini", "local", "remote"], "models": _env_models(), "rerankers": RERANKERS,
            "remote_url": os.environ.get("EMBEDDING_REMOTE_URL", "http://192.168.1.147:8002"),
            "default": {"backend": backend, "model": model.strip()},
            "corpora": [{"id": "rules", "label": "규칙 설명문 (지금 서비스)"}, {"id": "errors", "label": "틀린 예문 → 규칙"}, {"id": "both", "label": "예문 + 설명문 합침"}],
            "note": {"gemini": "무료 한도 하루 1,000회 — 시험지 문장 수 + 규칙 100 만큼 소모",
                     "local": "이 PC 의 CPU 로 계산 (sentence-transformers 설치 필요, 첫 실행은 모델 내려받기)",
                     "remote": "강의실 GPU 서버 (LAN 안에서만)"}}


def job_status() -> dict:
    return _status("embed")


def start_job(backend: str, model: str | None, rerank: str | None, topn: int, corpus: str = "rules") -> dict:
    corpus_kr = {"rules": "규칙 설명문", "errors": "틀린 예문", "both": "예문+설명문"}.get(corpus, corpus)
    label = (model or "gemini-embedding-001") + (f" · {corpus_kr}" if corpus != "rules" else "") + (f" + 재랭킹({rerank})" if rerank else "")
    cmd = [sys.executable, "-m", "tests.eval_embed", "--backend", backend, "--corpus", corpus]
    if model and backend != "gemini":
        cmd += ["--model", model]
    if rerank:
        cmd += ["--rerank", rerank, "--topn", str(max(5, min(topn, 30)))]
    return _start("embed", label, cmd)


# ── ② 튜터 평가 (/fix 끝까지) ───────────────────────────────────────────────
def fix_job_status() -> dict:
    return _status("fix")


def start_fix_job(backend: str, no_rag: bool, label: str = "", limit: int = 0, per_rule: int = 0, normal: int = -1, textbook: bool = True) -> dict:
    """tests/eval_fix.py --backend <b> [--no-rag] [--label] [--limit] [--per-rule n --normal n].
    per_rule=1, normal=20 이면 규칙당 1문장 + 정상 20 = 120문장 (전체 360 의 1/3 시간). label 은 파일명에 붙는 실행 이름."""
    clean = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (label or "").strip())
    cmd = [sys.executable, "-m", "tests.eval_fix", "--backend", backend]
    if no_rag:
        cmd.append("--no-rag")
    if not textbook:
        cmd.append("--no-textbook")
    if clean:
        cmd += ["--label", clean]
    if per_rule:
        cmd += ["--per-rule", str(per_rule)]
    if normal >= 0:
        cmd += ["--normal", str(normal)]
    if limit:
        cmd += ["--limit", str(limit)]
    size = f"규칙당 {per_rule}" + (f" + 정상 {normal}" if normal >= 0 else "") if per_rule else "전체"
    return _start("fix", f"{backend}" + (" · 검색 없음" if no_rag else " · RAG") + ("" if textbook else " · 교과서 검색 없음") + f" · {size}" + (f" · {clean}" if clean else ""), cmd)


def fix_history() -> dict:
    """fix_compare_*.json 전부 → 실행별 요약 + 지금 시험지와 짝이 맞는 것 중 최신 실행의 놓친 문장.
    시연 문장(--sentences) 실행은 정답이 없어 뺀다. same_sheet = 실행한 문장이 전부 지금 eval.csv 에 있음 (부분 평가 포함;
    옛 시험지 실행은 문장이 달라 빠진다). 부분 평가끼리는 n 이 같아야 직접 비교가 된다 — 표에 n 을 같이 보여 준다."""
    eval_rows = golden.eval_set()
    eval_n = len(eval_rows)
    eval_texts = {(r.get("text") or "").strip() for r in eval_rows}
    runs = []
    for path in sorted(OUT_DIR.glob("fix_compare_2*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if d.get("sentences") or not d.get("results"):
            continue
        res = d["results"]
        for b in d.get("backends") or []:
            js = [e["by"].get(b, {}) for e in res]
            n_err = sum(1 for e in res if not e["is_normal"])
            n_norm = sum(1 for e in res if e["is_normal"])
            judge = [j.get("judge", "") for j in js]
            hit = sum(1 for e, j in zip(res, judge) if not e["is_normal"] and j == "✓")
            missed = sum(1 for j in judge if j.startswith("✗ 놓침"))
            wrong = sum(1 for e, j in zip(res, judge) if not e["is_normal"] and j.startswith("✗") and not j.startswith("✗ 놓침"))
            kept = sum(1 for e, j in zip(res, judge) if e["is_normal"] and j.startswith("✓"))
            false_fix = sum(1 for j in judge if j.startswith("✗ 오교정"))
            fail = sum(1 for j in judge if j.startswith("!"))
            ms = [j.get("ms") for j in js if j.get("ms") and not j.get("error")]
            # 교과서 범위 지표 (eval_fix 가 used_pattern·outside_words 를 기록한 실행만): 고친 문장 중 교과서 패턴을 쓴 비율 · 학년 밖 단어가 든 비율
            fixed_js = [j for e, j in zip(res, js) if not e["is_normal"] and not j.get("error") and j.get("ok") is False]
            has_tb = any("used_pattern" in j for j in fixed_js)
            used_pattern = round(sum(1 for j in fixed_js if j.get("used_pattern")) / len(fixed_js), 4) if has_tb and fixed_js else None
            outside = round(sum(1 for j in fixed_js if j.get("outside_words")) / len(fixed_js), 4) if has_tb and fixed_js else None
            s = (d.get("summary") or {}).get(b) or {}
            runs.append({"file": path.name, "ran_at": d.get("ran_at"), "label": d.get("label") or "", "backend": b, "model": s.get("model"),
                         "no_rag": bool(d.get("no_rag")), "no_textbook": bool(d.get("no_textbook")), "condition": d.get("condition"), "embedding": (d.get("index") or {}).get("model"),
                         "used_pattern": used_pattern, "outside_words": outside,
                         "n": len(res), "n_err": n_err, "n_norm": n_norm,
                         "rule_acc": round(hit / n_err, 4) if n_err else None, "hit": hit, "missed": missed, "wrong_rule": wrong,
                         "normal_kept": round(kept / n_norm, 4) if n_norm else None, "false_fix": false_fix, "failures": fail,
                         "avg_ms": int(sum(ms) / len(ms)) if ms else None,
                         "same_sheet": all((e.get("text") or "").strip() in eval_texts for e in res)})
    same = [r for r in runs if r["same_sheet"]]
    latest_same = same[-1] if same else None
    misses = []
    if latest_same:
        d = json.loads((OUT_DIR / latest_same["file"]).read_text(encoding="utf-8"))
        b = latest_same["backend"]
        for e in d["results"]:
            j = e["by"].get(b, {})
            if j.get("judge", "").startswith("✓"):
                continue
            misses.append({"text": e["text"], "expected": e["expected"] or "정상", "judge": j.get("judge"), "rule_id": j.get("rule_id"),
                           "fixed": j.get("fixed"), "rank": j.get("rank"), "error": j.get("error")})
    return {"runs": runs, "latest": latest_same, "misses": misses, "sheet": {"n": eval_n, "n_norm": sum(1 for r in eval_rows if (r.get("expected_rule_id") or "").strip() == "NONE"),
                                                                            "hidden": len(runs) - len(same)}}
