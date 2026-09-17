"""STT 정확도(WER) 평가 — 관리자·실험실 "STT 정확도" 패널의 숫자를 만든다 (2026-09-17, 팀장).

두 가지 시험 세트를 같은 잣대로 잰다.
  1) 합성음 기준선: patterns.csv 문장을 Piper(backend/tts.py)로 읽어 wav 로 만든 것 → data/stt_eval/synth/<item_id>.wav + manifest.csv
     "STT 파이프라인이 깨끗한 소리를 얼마나 정확히 받아쓰나". 0 에 가까워야 정상. 아이 목소리 정확도가 아니다.
  2) 서비스 녹음: /speak 가 남기는 data/student/speak_log.jsonl (TTS 담당이 만들 것) 중 item_id 가 있는 행(따라 말하기)
     정답 = 패턴 원문, 들린 문장 = 로그의 heard. 이미 인식된 결과라 다시 돌리지 않는다 (--retranscribe 면 저장된 오디오로 다시 인식).

    python -m tests.eval_stt --make-synth [--limit N]      # Piper 로 합성음 세트 만들기 (이 PC, 패턴 477개 몇 분)
    python -m tests.eval_stt --run synth [--limit N]       # 합성음 세트를 Whisper(speak._transcribe: 서버 있으면 서버, 없으면 로컬)로 인식해 WER
    python -m tests.eval_stt --run service [--days 30]     # speak_log 의 따라 말하기 행으로 WER (아이 목소리)
결과: data/rag_eval/stt_eval_<시각>.json  {source, backend, model, n, wer, passed_rate, rows[...]}  → GET /api/admin/stt_history

WER(단어 오류율) = (틀린 + 빠진 + 더 들어간 단어) / 정답 단어 수. 대소문자·문장부호는 뗀다. 0.10 = 열 단어 중 하나 틀림.
speak_log.jsonl 한 줄 형식 (TTS 담당과 약속): {"ts","student","item_id","expected","heard","score","passed","language","backend","ms","audio"}
  audio = data/student/speak_audio/<파일명> (있으면 --retranscribe 가능). item_id 없는 자유 문장은 정답이 없어 WER 대상 아님.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import golden                                                 # noqa: E402

STT_DIR = ROOT / "data" / "stt_eval"
SYNTH_DIR = STT_DIR / "synth"
MANIFEST = STT_DIR / "manifest.csv"
OUT_DIR = ROOT / "data" / "rag_eval"
SPEAK_LOG = ROOT / "data" / "student" / "speak_log.jsonl"


# ── WER ──
_NUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
        "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100"}
_SPELL = {"grey": "gray", "colour": "color", "favourite": "favorite", "mum": "mom", "ok": "okay"}


def _words(text: str) -> list[str]:
    """비교용 낱말: 소문자 · 문장부호 제거 · 숫자는 아라비아 숫자로 통일(twelve→12) · $10 → 10 dollars · 영/미 철자 통일.
    Whisper 가 'twelve years' 를 '12 years' 로 적는 건 받아쓰기 오류가 아니라서 (합성음 475개에서 틀린 10단어 중 6개가 이것)."""
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"\$\s*(\d+)", r"\1 dollars", t)
    out = []
    for w in re.findall(r"[a-z0-9']+", t):
        w = _NUM.get(w, w); w = _SPELL.get(w, w)
        out.append(w)
    return out


def wer(reference: str, hypothesis: str) -> tuple[float, int, int]:
    """(WER, 오류 단어 수, 정답 단어 수). 정답이 비면 (0, 0, 0). 단어 단위 편집 거리."""
    r, h = _words(reference), _words(hypothesis)
    if not r:
        return 0.0, 0, 0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (0 if r[i - 1] == h[j - 1] else 1))
            prev = cur
    return d[len(h)] / len(r), d[len(h)], len(r)


# ── 합성음 세트 ──
def make_synth(limit: int = 0) -> int:
    """patterns.csv 전부를 Piper 로 wav 로 만들고 manifest.csv 를 쓴다. 이미 있는 파일은 건너뛴다."""
    from backend import tts
    from backend.config import settings
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    rows = golden.all_patterns()
    if limit:
        rows = rows[:limit]
    made = 0
    t0 = time.time()
    for i, p in enumerate(rows, 1):
        dst = SYNTH_DIR / f"{p['id']}.wav"
        if not dst.exists():
            src = tts.ensure_tts(p["id"], p["text"])          # audio_cache/<id>.wav (서비스 캐시와 같은 파일)
            dst.write_bytes(Path(src).read_bytes())
            made += 1
        if i % 50 == 0 or i == len(rows):
            print(f"[eval_stt] 합성 {i}/{len(rows)} (새로 만든 것 {made}, {int(time.time() - t0)}초)", flush=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "item_id", "text", "speaker", "level", "unit", "note"])
        for p in rows:
            w.writerow([f"synth/{p['id']}.wav", p["id"], "", "piper:" + settings.piper_voice_name, p.get("level", ""), p.get("unit", ""), "합성음"])   # level·unit 은 all_patterns 에 없으면 빈칸
    print(f"[eval_stt] manifest {MANIFEST} · {len(rows)}행 · 목소리 {settings.piper_voice_name}", flush=True)
    return len(rows)


def _reference(item_id: str, text: str) -> str:
    if text:
        return text
    it = golden.find_item(item_id) if item_id else None
    return (it or {}).get("text", "")


def run_synth(limit: int = 0) -> dict:
    """manifest 의 wav 를 speak._transcribe 로 인식해 WER. speak.py 는 읽기 전용으로 함수만 빌린다."""
    from backend import speak
    if not MANIFEST.exists():
        sys.exit("[eval_stt] manifest 가 없어요 — 먼저 --make-synth")
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    if limit:
        rows = rows[:limit]
    backend = "whisper-server" if speak.WHISPER_SERVER_URL else "whisper-local"
    model = "large-v3" if speak.WHISPER_SERVER_URL else __import__("os").environ.get("WHISPER_MODEL", "base")
    print(f"[eval_stt] 합성음 {len(rows)}개 · {backend} ({model})", flush=True)
    out_rows, t_all = [], time.time()
    for i, r in enumerate(rows, 1):
        ref = _reference(r.get("item_id", ""), r.get("text", ""))
        path = STT_DIR / r["file"]
        t0 = time.time()
        try:
            b64 = base64.b64encode(path.read_bytes()).decode()
            heard, conf = speak._transcribe(b64, "audio/wav", "en")
            err = None
        except Exception as e:  # noqa: BLE001
            heard, conf, err = "", -999.0, str(e)[:120]
        w, bad, n = wer(ref, heard)
        out_rows.append({"file": r["file"], "item_id": r.get("item_id", ""), "speaker": r.get("speaker", ""), "expected": ref, "heard": heard,
                         "wer": round(w, 3), "errors": bad, "words": n, "score": speak.similarity(heard, ref), "ms": int((time.time() - t0) * 1000), "error": err})
        if i % 25 == 0 or i == len(rows):
            done = out_rows
            print(f"  [{i}/{len(rows)}] WER 누적 {sum(x['errors'] for x in done) / max(1, sum(x['words'] for x in done)):.3f} · {int(time.time() - t_all)}초", flush=True)
    return _save("synth", backend, model, out_rows)


def run_service(days: int = 30, retranscribe: bool = False) -> dict:
    """speak_log 의 item_id 있는 행(따라 말하기) → 정답 = 패턴 원문, 들린 문장 = 로그 heard. 자유 문장은 정답이 없어 제외."""
    if not SPEAK_LOG.exists():
        sys.exit(f"[eval_stt] {SPEAK_LOG.relative_to(ROOT)} 가 없어요 — TTS 담당이 /speak 로그를 남기면 생겨요")
    since = datetime.now() - timedelta(days=days)
    rows, skipped = [], 0
    for line in SPEAK_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            ts = datetime.fromisoformat(r.get("ts", ""))
        except ValueError:
            continue
        if ts < since:
            continue
        if not r.get("item_id"):
            skipped += 1
            continue
        rows.append(r)
    backend, model = "speak_log", ""
    out_rows = []
    speak = None
    if retranscribe:
        from backend import speak as _sp
        speak = _sp
        backend = "whisper-server" if speak.WHISPER_SERVER_URL else "whisper-local"
    for r in rows:
        ref = _reference(r.get("item_id", ""), r.get("expected", ""))
        heard = r.get("heard", "")
        err = None
        if retranscribe and r.get("audio"):
            try:
                b64 = base64.b64encode((ROOT / r["audio"]).read_bytes()).decode()
                heard, _ = speak._transcribe(b64, "audio/webm" if str(r["audio"]).endswith(".webm") else "audio/wav", r.get("language") or "en")
            except Exception as e:  # noqa: BLE001
                err = str(e)[:120]
        w, bad, n = wer(ref, heard)
        out_rows.append({"file": r.get("audio", ""), "item_id": r.get("item_id", ""), "speaker": r.get("student", ""), "expected": ref, "heard": heard,
                         "wer": round(w, 3), "errors": bad, "words": n, "score": r.get("score"), "passed": r.get("passed"), "ms": r.get("ms"), "ts": r.get("ts"), "error": err})
    print(f"[eval_stt] 서비스 녹음 {len(out_rows)}행 (자유 문장 {skipped}행 제외) · 최근 {days}일", flush=True)
    return _save("service", backend, model, out_rows, extra={"days": days, "skipped_free": skipped})


def _save(source: str, backend: str, model: str, rows: list[dict], extra: dict | None = None) -> dict:
    words = sum(r["words"] for r in rows); errors = sum(r["errors"] for r in rows)
    passed = [r for r in rows if r.get("score") is not None]
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"), "source": source, "backend": backend, "model": model,
           "n": len(rows), "words": words, "errors": errors, "wer": round(errors / words, 4) if words else None,
           "passed_rate": round(sum(1 for r in passed if (r.get("passed") if r.get("passed") is not None else (r["score"] or 0) >= 70)) / len(passed), 3) if passed else None,
           "worst": sorted([r for r in rows if r["words"]], key=lambda r: -r["wer"])[:20], "rows": rows, **(extra or {})}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"stt_eval_{datetime.now():%Y%m%d-%H%M}_{source}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[eval_stt] {source}: WER {out['wer']} ({errors}/{words} 단어) · {len(rows)}개 · 통과율 {out['passed_rate']}", flush=True)
    print(f"저장: {path}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-synth", action="store_true", help="Piper 로 합성음 세트 만들기")
    ap.add_argument("--run", choices=["synth", "service"], help="어느 세트를 잴지")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--days", type=int, default=30, help="service: 최근 n일")
    ap.add_argument("--retranscribe", action="store_true", help="service: 저장된 오디오로 다시 인식 (기본은 로그의 heard 그대로)")
    a = ap.parse_args()
    if a.make_synth:
        make_synth(a.limit)
    if a.run == "synth":
        run_synth(a.limit)
    elif a.run == "service":
        run_service(a.days, a.retranscribe)
    if not a.make_synth and not a.run:
        ap.print_help()


if __name__ == "__main__":
    main()
