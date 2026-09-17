"""
생성 점검 — "우리 규칙으로 못 짚은 문장" 찾기   담당: 팀장

LLM 으로 초등학생 문장을 만들고(절반은 우리 규칙 안 오류, 절반은 규칙 밖 오류) 실제 /fix 경로(tutor.diagnose)로 진단해
결과를 학생 로그(student=GEN)와 data/rag_eval/gen_gaps_<시각>.json (+ _latest) 에 남긴다.
관리자 화면 "우리 규칙으로 못 짚은 문장" 표와 "생성 점검 문장" 표, tests/gen_gaps.py(명령줄) 가 이 모듈을 쓴다.

- 만든 모델이 붙인 오류 이름은 '모델 표시' 일 뿐이다. 맞는 문장에 오류 이름을 붙이기도 하므로 데이터팀이 확인해야 한다.
- 모델은 규칙 밖 오류를 잘 지적하지 않아 OTHER 로는 거의 안 나온다. "밖 오류로 만들었는데 튜터가 맞다고 한 문장" 이 빠진 규칙 후보다.
- 한 번에 한 작업만 돈다(관리자 화면 버튼). Gemini 무료 등급은 분당 한도가 있어 gemini 면 문장 사이 5초 쉰다.
"""
from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from backend import golden, llm, tutor
from backend.config import settings

OUT_DIR = golden.ROOT / "data" / "rag_eval"
LATEST = OUT_DIR / "gen_gaps_latest.json"
OUTSIDE = ["to부정사 (want to go, nice to meet you)", "동사 겹쳐 쓰기 (I went to go)", "전치사 (in the morning, at school)",
           "의문문 어순 (Do you like…? / What is…?)", "부정문 (don't, doesn't, isn't)", "대명사 격 (me/I, him/he)",
           "비교급 (bigger than)", "some/any", "can/can't 위치", "There is/are 뒤 명사 수", "철자 실수"]

_job: dict = {"running": False, "started": None, "done": 0, "total": 0, "backend": None, "error": None, "log": []}
_job_lock = threading.Lock()


def generate(n: int, backend: str | None = None) -> list[dict]:
    """문장 n개 생성 → [{text, error, inside, correct}]. correct = 만든 모델이 생각하는 맞는 문장 (원문과 같으면 고칠 게 없다고 본 것)."""
    types = sorted({r["type"] for r in golden.rules()})
    prompt = f"""한국 초등학생(3~6학년)이 영어로 말하거나 쓸 법한 짧은 문장 {n}개를 만들어라. 각 문장은 문법 오류가 정확히 하나 있다.
절반은 아래 "우리 규칙" 목록 안의 오류, 절반은 목록에 **없는** 오류(예: {', '.join(OUTSIDE)})로 만든다.
단어는 쉬운 초등 단어만. 5~9단어. 같은 오류 유형을 두 번 넘게 쓰지 않는다. 주제는 학교·가족·동물·음식·날씨·주말 등 다양하게.
정말로 틀린 문장만 만든다. 맞는 문장에 오류 이름을 붙이지 않는다.

우리 규칙 유형: {', '.join(types)}

출력은 JSON 하나만:
{{"sentences": [{{"text": "틀린 문장", "correct": "맞게 고친 문장", "error": "오류 유형 한국어 한 줄", "inside": true 또는 false}}, ...]}}"""
    out = llm.generate_json(prompt, backend=backend)
    rows = [r for r in out.get("sentences", []) if isinstance(r, dict) and r.get("text")]
    random.shuffle(rows)
    return rows[:n]


def run_check(n: int = 20, backend: str | None = None, student: str = "GEN", sleep: float | None = None, progress=None) -> dict:
    """생성 → /fix 진단 → 파일 저장. progress(i, total, line) 로 진행 상황을 알린다. 반환: 저장한 결과 dict."""
    backend = backend or settings.llm_backend
    sleep = sleep if sleep is not None else (5.0 if backend == "gemini" else 0.0)
    model = llm._model_of(backend)
    rows = generate(n, backend)
    units = [u["unit"] for u in golden.units(3)] or [""]
    tally = {"ok": 0, "rule": 0, "OTHER": 0, "fail": 0, "llm_err": 0}
    results = []
    for i, r in enumerate(rows, 1):
        text, unit = r["text"].strip(), random.choice(units)
        if i > 1 and sleep:
            time.sleep(sleep)
        try:
            res = tutor.diagnose(text, level=3, unit=unit, student=student, source_kind="gen", record=True, backend=backend)
            if res["ok"]:
                kind, detail = "ok", ("철자 " + ", ".join(f"{s['wrong']}→{s['fix']}" for s in res["spelling"])) if res.get("spelling") else ""
            elif res["rule"] and res["rule"]["id"] == "OTHER":
                kind, detail = "OTHER", f"→ {res['fixed']}"
            else:
                kind, detail = "rule", f"{res['rule']['id']} {res['rule']['name']}: {res['wrong']} → {res['fix']}"
        except HTTPException as e:                            # 검증 실패(502, 로그에 남음) 와 LLM 호출 오류(429 등, 로그에 안 남음) 구분
            msg = str(e.detail)
            kind, detail = ("fail", msg[:120]) if msg.startswith("모델") else ("llm_err", msg[:100])
        except llm.LLMError as e:
            kind, detail = "llm_err", str(e)[:100]
        tally[kind] += 1
        row = {"text": text, "unit": unit, "intended": r.get("error", ""), "inside": bool(r.get("inside")), "correct": (r.get("correct") or "").strip(),
               "result": kind, "detail": detail}
        results.append(row)
        if progress:
            progress(i, len(rows), row)
    missed = [x for x in results if not x["inside"] and x["result"] == "ok"]
    out = {"backend": backend, "model": model, "ran_at": datetime.now().isoformat(timespec="seconds"), "student": student,
           "tally": tally, "missed_outside": missed, "results": results}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"gen_gaps_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    LATEST.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    out["path"] = str(path.relative_to(golden.ROOT)).replace("\\", "/")
    return out


def latest() -> dict | None:
    if not LATEST.exists():
        return None
    try:
        return json.loads(LATEST.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


# ── 관리자 화면 버튼용 백그라운드 작업 (한 번에 하나) ──
def delete(indices: list[int] | None = None, everything: bool = False) -> dict:
    """생성 점검 결과 지우기 (9/17). everything=True: 결과 파일 전부(gen_gaps_*.json + _latest) 와 학생 GEN 의 sentence_log 행·notebook 항목을 지운다.
    indices: 최근 결과(_latest)에서 그 번호(0부터)의 문장만 빼고, 그 문장의 GEN 로그 행도 지운다. 시간 파일은 같은 ran_at 의 것을 같이 고친다.
    사람 학생(A·B …)의 기록은 어떤 경우에도 건드리지 않는다."""
    log_path = tutor.STUDENT_DIR / "sentence_log.jsonl"
    nb_path = tutor.STUDENT_DIR / "notebook.json"
    student = "GEN"

    def _prune_log(keep_fn) -> int:
        if not log_path.exists():
            return 0
        with tutor._lock:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            kept, removed = [], 0
            for line in lines:
                try:
                    row = json.loads(line) if line.strip() else None
                except ValueError:
                    row = None
                if row is not None and row.get("student") == student and not keep_fn(row):
                    removed += 1
                    continue
                kept.append(line)
            log_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        return removed

    if everything:
        files = sorted(OUT_DIR.glob("gen_gaps_*.json"))
        for f in files:
            f.unlink()
        removed = _prune_log(lambda row: False)
        if nb_path.exists():
            with tutor._lock:
                try:
                    nb = json.loads(nb_path.read_text(encoding="utf-8"))
                except ValueError:
                    nb = {}
                if student in nb:
                    nb.pop(student)
                    nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"deleted_files": len(files), "deleted_log_rows": removed, "latest": None}

    g = latest()
    if not g or not g.get("results"):
        return {"deleted_files": 0, "deleted_log_rows": 0, "latest": g}
    drop = {i for i in (indices or []) if 0 <= i < len(g["results"])}
    if not drop:
        return {"deleted_files": 0, "deleted_log_rows": 0, "latest": g}
    gone_texts = {g["results"][i]["text"] for i in drop}
    g["results"] = [r for i, r in enumerate(g["results"]) if i not in drop]
    g["tally"] = {k: sum(1 for r in g["results"] if r["result"] == k) for k in ("ok", "rule", "OTHER", "fail", "llm_err")}
    g["missed_outside"] = [x for x in g["results"] if not x["inside"] and x["result"] == "ok"]
    text = json.dumps(g, ensure_ascii=False, indent=1)
    LATEST.write_text(text, encoding="utf-8")
    for f in OUT_DIR.glob("gen_gaps_*.json"):                 # 같은 실행의 시간 파일도 맞춰 둔다 (ran_at 으로 찾음)
        if f == LATEST:
            continue
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("ran_at") == g.get("ran_at"):
                f.write_text(text, encoding="utf-8")
        except (ValueError, OSError):
            pass
    removed = _prune_log(lambda row: (row.get("text") or "").strip() not in gone_texts)
    return {"deleted_files": 0, "deleted_log_rows": removed, "latest": g}


def job_status() -> dict:
    with _job_lock:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _job.items()}


def start_job(n: int, backend: str | None) -> dict:
    with _job_lock:
        if _job["running"]:
            raise HTTPException(409, "이미 돌고 있어요. 끝나면 다시 눌러 주세요.")
        _job.update(running=True, started=datetime.now().isoformat(timespec="seconds"), done=0, total=n, backend=backend or settings.llm_backend, error=None, log=[])

    def progress(i, total, row):
        with _job_lock:
            _job["done"], _job["total"] = i, total
            _job["log"].append(f"[{i}/{total}] {row['result']} {row['text']}")

    def work():
        try:
            run_check(n=n, backend=backend, progress=progress)
        except Exception as e:  # noqa: BLE001 — 화면에 이유를 보여주고 끝낸다
            with _job_lock:
                _job["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        finally:
            with _job_lock:
                _job["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return job_status()
