"""tests/manual_chat_sessions.txt 를 실제 backend.ask.ask()로 돌려서 결과표를 뽑는다
(TTS 담당 소유, 수동 QA용 — pytest 대상 아님).

실행 (project 폴더에서, 가상환경 활성화 후):
    python -m tests.run_manual_sessions

세션(같은 학생) 안에서는 순서대로 호출해 대화 맥락(180초 윈도우)이 이어지게 한다.
[오답노트] 태그가 있는 세션은 student="A"로 고정해 실제 오답노트 데이터를 쓴다(그 외엔
세션 번호로 만든 가상 student id).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.ask import ask, AskIn, AskContext  # noqa: E402

SRC = ROOT / "tests" / "manual_chat_sessions.txt"
OUT = ROOT / "tests" / "manual_chat_sessions_result.csv"

LINE_RE = re.compile(r"^(?P<q>[^#]+?)\s*(?:#\s*(?P<tag>.+))?$")
SESSION_RE = re.compile(r"^#\s*──\s*세션\s*(\d+)")


def parse_sessions() -> list[tuple[int, list[tuple[str, str]]]]:
    sessions: list[tuple[int, list[tuple[str, str]]]] = []
    current: list[tuple[str, str]] | None = None
    current_num = 0
    for raw in SRC.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = SESSION_RE.match(line)
        if m:
            if current is not None:
                sessions.append((current_num, current))
            current_num = int(m.group(1))
            current = []
            continue
        if line.startswith("#"):
            continue
        mm = LINE_RE.match(line)
        if not mm or not mm.group("q").strip():
            continue
        q = mm.group("q").strip()
        tag = (mm.group("tag") or "").strip()
        if current is None:
            current = []
        current.append((q, tag))
    if current:
        sessions.append((current_num, current))
    return sessions


def run() -> None:
    sessions = parse_sessions()
    total = sum(len(items) for _, items in sessions)
    print(f"세션 {len(sessions)}개, 문항 {total}개 로드됨\n")

    rows: list[dict] = []
    done = 0
    for sess_num, items in sessions:
        has_notebook = any("오답노트" in tag for _, tag in items)
        student = "A" if has_notebook else f"M{sess_num:02d}"
        for q, tag in items:
            ctx = AskContext(screen="notebook") if "오답노트" in tag else AskContext()
            try:
                r = ask(AskIn(student=student, question=q, context=ctx))
                answer = r.get("answer", "")
                offtopic = r.get("offtopic")
                sources = ",".join(s.get("chunk_id", "") for s in r.get("source", []))
                error = ""
            except Exception as e:  # noqa: BLE001
                answer, offtopic, sources = "", None, ""
                error = f"{type(e).__name__}: {e}"
            rows.append({
                "session": sess_num,
                "student": student,
                "tag": tag,
                "question": q,
                "offtopic": offtopic,
                "sources": sources,
                "answer": answer.replace("\n", " ")[:200],
                "error": error,
            })
            done += 1
            status = "ERR" if error else ("OFF" if offtopic else "ok")
            print(f"[{done:3d}/{total}] S{sess_num:02d} {status:>3} | {q[:40]:40s} | {answer[:50].replace(chr(10),' ')}")

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["session", "student", "tag", "question", "offtopic", "sources", "answer", "error"])
        w.writeheader()
        w.writerows(rows)

    n_off = sum(1 for r in rows if r["offtopic"] is True)
    n_err = sum(1 for r in rows if r["error"])
    print(f"\n=== 요약 === 총 {len(rows)}건 | offtopic={n_off} | 에러={n_err}")
    print(f"결과표 저장: {OUT}")
    if n_err:
        print("\n에러 목록:")
        for r in rows:
            if r["error"]:
                print(f"  S{r['session']:02d} {r['question']!r}: {r['error']}")


if __name__ == "__main__":
    run()
