"""tests/stt_test_sentences.txt 를 edge-tts로 합성 → 실제 hybrid_stt()로 돌려서 결과표를 뽑는다
(TTS 담당 소유, 수동 QA용 — pytest 대상 아님. 실제 사람 목소리가 아니라 합성 음성이라 "병합
로직이 안 깨지는지" 확인용이지 진짜 인식 정확도 측정은 아니다).

실행 (project 폴더에서, 가상환경 활성화 후):
    python -m tests.run_stt_sentences
"""
from __future__ import annotations

import asyncio
import base64
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import edge_tts  # noqa: E402
import backend.speak as speak  # noqa: E402

SRC = ROOT / "tests" / "stt_test_sentences.txt"
OUT = ROOT / "tests" / "stt_test_sentences_result.csv"
VOICE = "ko-KR-HyunsuMultilingualNeural"

CATEGORY_RE = re.compile(r"^#\s*──\s*\[(.+?)\]")


async def tts_mp3_bytes(text: str) -> bytes:
    comm = edge_tts.Communicate(text, voice=VOICE)
    chunks = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            chunks.extend(chunk["data"])
    return bytes(chunks)


def parse_sentences() -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    category = "?"
    for raw in SRC.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = CATEGORY_RE.match(line)
        if m:
            category = m.group(1)
            continue
        if line.startswith("#"):
            continue
        items.append((category, line))
    return items


def run() -> None:
    items = parse_sentences()
    total = len(items)
    print(f"문장 {total}개 로드됨\n")

    rows: list[dict] = []
    for i, (category, text) in enumerate(items, start=1):
        t0 = time.perf_counter()
        try:
            mp3 = asyncio.run(tts_mp3_bytes(text))
            heard = speak.hybrid_stt(base64.b64encode(mp3).decode(), "audio/mp3", student=f"STT100_{i}")
            error = ""
        except Exception as e:  # noqa: BLE001
            heard, error = "", f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        rows.append({"idx": i, "category": category, "input": text, "heard": heard, "error": error, "sec": round(dt, 1)})
        match = "==" if heard.strip() == text.strip() else "~="
        print(f"[{i:3d}/{total}] ({dt:5.1f}s) [{category}] {text[:30]:30s} {match} {heard!r}" + (f"  ERR:{error}" if error else ""))

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "category", "input", "heard", "error", "sec"])
        w.writeheader()
        w.writerows(rows)

    n_exact = sum(1 for r in rows if r["heard"].strip() == r["input"].strip())
    n_err = sum(1 for r in rows if r["error"])
    total_sec = sum(r["sec"] for r in rows)
    print(f"\n=== 요약 === 총 {len(rows)}건 | 원문과 완전 동일={n_exact} | 에러={n_err} | 총 소요={total_sec/60:.1f}분")
    print(f"결과표 저장: {OUT}")


if __name__ == "__main__":
    run()
