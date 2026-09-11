"""
관리자 화면 [검색 평가 실행] — 임베딩 모델(+재랭킹)을 골라 tests/eval_embed.py 를 백그라운드 서브프로세스로 돌린다.
(팀장 · 2026-09-11. 생성 점검(gapcheck.py)과 같은 "시작 → 진행률 폴링" 방식)

서브프로세스인 이유: backend/embedding.py 가 import 시점에 .env 의 모델을 고정해서, 서버 프로세스 안에서는 다른 모델을
못 쓴다. 별도 프로세스에 환경변수만 덮어써서 돌리면 .env 도, 서비스가 쓰는 data/chroma 색인도 그대로다.

선택지(options): .env 의 임베딩 표(### 모델 이름 ... %)에서 모델 이름을 읽고, 없으면 .env.example → 기본 목록 순.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_MODELS = ["intfloat/multilingual-e5-base", "all-MiniLM-L6-v2", "intfloat/multilingual-e5-large",
                   "all-mpnet-base-v2", "BAAI/bge-m3", "paraphrase-multilingual-mpnet-base-v2", "paraphrase-multilingual-MiniLM-L12-v2"]
RERANKERS = ["BAAI/bge-reranker-v2-m3", "BAAI/bge-reranker-base", "cross-encoder/ms-marco-MiniLM-L-6-v2"]
_MODEL_LINE = re.compile(r"^#+\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+|all-[A-Za-z0-9_.\-]+|paraphrase-[A-Za-z0-9_.\-]+)\s+\d+(\.\d+)?%")

_job: dict = {"running": False, "started": None, "done": 0, "total": 0, "label": None, "error": None, "log": [], "result_file": None}
_lock = threading.Lock()


def _env_models() -> list[str]:
    """`.env`(없으면 .env.example)의 모델 표에서 이름을 읽는다. 표가 없으면 기본 목록."""
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
    """화면 선택지. 지금 .env 가 가리키는 백엔드·모델을 default 로 표시."""
    backend = os.environ.get("EMBEDDING_BACKEND", "gemini").strip().lower()
    model = {"gemini": "gemini-embedding-001", "local": os.environ.get("EMBEDDING_LOCAL_MODEL", "intfloat/multilingual-e5-base"),
             "remote": os.environ.get("EMBEDDING_REMOTE_MODEL", "intfloat/multilingual-e5-base")}.get(backend, "?")
    return {"backends": ["gemini", "local", "remote"], "models": _env_models(), "rerankers": RERANKERS,
            "remote_url": os.environ.get("EMBEDDING_REMOTE_URL", "http://192.168.1.147:8002"),
            "default": {"backend": backend, "model": model.strip()},
            "note": {"gemini": "무료 한도 하루 1,000회 — 시험지 문장 수 + 규칙 100 만큼 소모",
                     "local": "이 PC 의 CPU 로 계산 (sentence-transformers 설치 필요, 첫 실행은 모델 내려받기)",
                     "remote": "강의실 GPU 서버 (LAN 안에서만)"}}


def job_status() -> dict:
    with _lock:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _job.items()}


def start_job(backend: str, model: str | None, rerank: str | None, topn: int) -> dict:
    with _lock:
        if _job["running"]:
            return job_status()
        label = (model or "gemini-embedding-001") + (f" + 재랭킹({rerank})" if rerank else "")
        _job.update(running=True, started=datetime.now().isoformat(timespec="seconds"), done=0, total=0, label=label, error=None, log=[], result_file=None)

    cmd = [sys.executable, "-m", "tests.eval_embed", "--backend", backend]
    if model and backend != "gemini":
        cmd += ["--model", model]
    if rerank:
        cmd += ["--rerank", rerank, "--topn", str(max(5, min(topn, 30)))]

    def run() -> None:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        try:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()
                if not line or "Warning" in line or "Loading weights" in line:
                    continue
                m = re.match(r"\[(\d+)/(\d+)\]", line)
                with _lock:
                    if m:
                        _job["done"], _job["total"] = int(m.group(1)), int(m.group(2))
                    m2 = re.search(r"저장: (retrieval_eval_\S+\.json)", line)
                    if m2:
                        _job["result_file"] = m2.group(1)
                    _job["log"].append(line[:200])
                    if len(_job["log"]) > 400:
                        del _job["log"][:-300]
            code = proc.wait()
            with _lock:
                if code != 0 and not _job["error"]:
                    tail = " / ".join(_job["log"][-3:])
                    _job["error"] = f"종료 코드 {code}: {tail[:300]}"
        except Exception as e:  # noqa: BLE001
            with _lock:
                _job["error"] = f"{type(e).__name__}: {e}"
        finally:
            with _lock:
                _job["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return job_status()
