"""주간 리포트 (BigQuery) — 관리자 패널용. docs/plan-B/bigquery-report-plan.md (2026-09-10) 의 2-2 · 2-3.

GET /api/admin/report?days=7[&source=auto|bq|file]
  집계 3개 (규칙별 걸린 횟수·학생 수 / 일별 문장 수·맞음 비율 / 학생별 상위 3 규칙) + LLM 이 쓴 "선생님께 보내는 주간 리포트 4문장".
  - source=bq   : BigQuery SQL 로 집계 (표 `sentence_log` 는 tests/bq_upload.py 가 올린다). 파일 집계와 행 수를 맞춰 본다 (file_n vs bq_n).
  - source=file : 서버 파일 data/student/sentence_log.jsonl 을 파이썬으로 같은 정의로 집계 (BigQuery 설정 전에도 패널이 돌게).
  - source=auto : .env 에 BQ_PROJECT 가 있으면 bq, 없으면 file. (기본)
  BigQuery 를 골랐는데 설정이 없으면 503 과 안내 문구.

.env: BQ_PROJECT=<gcp 프로젝트 id>  BQ_DATASET=elem_english  BQ_TABLE=sentence_log  BQ_LOCATION=asia-northeast3
      GOOGLE_APPLICATION_CREDENTIALS=<서비스 계정 키 json 경로 — git 밖>
서비스 동작(/fix, 오답노트)은 건드리지 않는다. 실시간 적재도 하지 않는다 (키·네트워크 의존이 서비스에 안 들어오게).
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend import golden, llm, tutor

router = APIRouter(prefix="/admin", tags=["admin"])

PROMPT_FILE = Path(__file__).parent / "prompts" / "report.txt"

BQ_PROJECT = os.environ.get("BQ_PROJECT", "").strip()
BQ_DATASET = os.environ.get("BQ_DATASET", "elem_english").strip() or "elem_english"
BQ_TABLE = os.environ.get("BQ_TABLE", "sentence_log").strip() or "sentence_log"
BQ_LOCATION = os.environ.get("BQ_LOCATION", "asia-northeast3").strip() or "asia-northeast3"


def bq_configured() -> bool:
    return bool(BQ_PROJECT)


def table_ref() -> str:
    return f"`{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`"


# ─────────────────────────────────────────────
# 파일 집계 (BigQuery SQL 과 같은 정의)
# ─────────────────────────────────────────────
EXCLUDED_STUDENTS = {"GEN"}          # 실험실 "생성 점검"이 만든 문장의 학생 id — 진짜 학생이 아니라 집계에서 제외 (파일 집계·SQL 둘 다)


def _file_rows(days: int) -> list[dict]:
    path = tutor.STUDENT_DIR / "sentence_log.jsonl"
    since = datetime.now() - timedelta(days=days)
    rows: list[dict] = []
    if not path.exists():
        return rows
    with tutor._lock, path.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                ts = datetime.fromisoformat(r.get("ts", ""))
            except ValueError:
                continue
            if ts >= since and (r.get("student") or "") not in EXCLUDED_STUDENTS:   # 실험용 학생(GEN)은 선생님 리포트에서 뺀다
                rows.append(r)
    return rows


def _rule_name(rid: str) -> str:
    return (golden.find_rule(rid) or {}).get("type", rid)


def aggregate_file(rows: list[dict]) -> dict:
    """규칙별 / 일별 / 학생별 상위 3 — SQL 3개와 같은 정의. 맞은 문장(ok=true)은 일별 개수·맞음 비율에만 들어간다."""
    by_rule: dict[str, dict] = {}
    by_day: dict[str, dict] = defaultdict(lambda: {"n": 0, "ok_n": 0})
    by_student: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        day = (r.get("ts") or "")[:10]
        by_day[day]["n"] += 1
        if r.get("ok"):
            by_day[day]["ok_n"] += 1
            continue
        rid = r.get("rule_id")
        if not rid:
            continue
        g = by_rule.setdefault(rid, {"rule_id": rid, "count": 0, "students": set()})
        g["count"] += 1
        g["students"].add(r.get("student") or "?")
        by_student[r.get("student") or "?"][rid] += 1
    rules = sorted(({"rule_id": g["rule_id"], "name": _rule_name(g["rule_id"]), "count": g["count"], "students": len(g["students"])}
                    for g in by_rule.values()), key=lambda g: (-g["count"], g["rule_id"]))
    days_out = [{"day": d, "n": v["n"], "ok_n": v["ok_n"], "ok_rate": round(v["ok_n"] / v["n"], 3) if v["n"] else 0.0}
                for d, v in sorted(by_day.items())]
    students = []
    for st, cnt in sorted(by_student.items()):
        top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        students.append({"student": st, "top": [{"rule_id": rid, "name": _rule_name(rid), "count": c} for rid, c in top]})
    return {"rules": rules, "days": days_out, "students": students, "n": len(rows)}


# ─────────────────────────────────────────────
# BigQuery 집계 (SQL 3개)
# ─────────────────────────────────────────────
SQL_RULES = """
SELECT rule_id, COUNT(*) AS count, COUNT(DISTINCT student) AS students
FROM {t}
WHERE ts >= @since AND ok = FALSE AND rule_id IS NOT NULL AND student NOT IN UNNEST(@excluded)
GROUP BY rule_id ORDER BY count DESC, rule_id
"""
SQL_DAYS = """
SELECT FORMAT_DATE('%Y-%m-%d', DATE(ts, @tz)) AS day, COUNT(*) AS n, COUNTIF(ok) AS ok_n
FROM {t}
WHERE ts >= @since AND student NOT IN UNNEST(@excluded)
GROUP BY day ORDER BY day
"""
SQL_STUDENTS = """
SELECT student, rule_id, count FROM (
  SELECT student, rule_id, COUNT(*) AS count,
         ROW_NUMBER() OVER (PARTITION BY student ORDER BY COUNT(*) DESC, rule_id) AS rk
  FROM {t}
  WHERE ts >= @since AND ok = FALSE AND rule_id IS NOT NULL AND student NOT IN UNNEST(@excluded)
  GROUP BY student, rule_id
) WHERE rk <= 3 ORDER BY student, rk
"""
SQL_COUNT = "SELECT COUNT(*) AS n FROM {t} WHERE ts >= @since AND student NOT IN UNNEST(@excluded)"


def _bq_client():
    try:
        from google.cloud import bigquery                                  # noqa: WPS433 — 설정한 사람만 필요
    except ImportError as e:
        raise HTTPException(503, "google-cloud-bigquery 패키지가 없어요. pip install google-cloud-bigquery") from e
    try:
        return bigquery, bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    except Exception as e:                                               # 키 파일 없음·권한 등
        raise HTTPException(503, f"BigQuery 인증 실패: {e} — .env 의 GOOGLE_APPLICATION_CREDENTIALS 확인") from e


def aggregate_bq(days: int) -> dict:
    bigquery, client = _bq_client()
    since = datetime.now() - timedelta(days=days)
    params = [bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
              bigquery.ScalarQueryParameter("tz", "STRING", "Asia/Seoul"),
              bigquery.ArrayQueryParameter("excluded", "STRING", sorted(EXCLUDED_STUDENTS))]
    t = table_ref()

    def run(sql: str) -> list[dict]:
        job = client.query(sql.format(t=t), job_config=bigquery.QueryJobConfig(query_parameters=params))
        return [dict(r) for r in job.result()]

    try:
        rules = run(SQL_RULES)
        days_rows = run(SQL_DAYS)
        st_rows = run(SQL_STUDENTS)
        n = run(SQL_COUNT)[0]["n"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"BigQuery 조회 실패: {e} — 표 {t} 가 있는지(tests/bq_upload.py) 확인") from e
    for r in rules:
        r["name"] = _rule_name(r["rule_id"])
    for d in days_rows:
        d["ok_rate"] = round(d["ok_n"] / d["n"], 3) if d["n"] else 0.0
    students: dict[str, list] = defaultdict(list)
    for r in st_rows:
        students[r["student"]].append({"rule_id": r["rule_id"], "name": _rule_name(r["rule_id"]), "count": r["count"]})
    return {"rules": rules, "days": days_rows, "students": [{"student": s, "top": v} for s, v in sorted(students.items())], "n": int(n)}


# ─────────────────────────────────────────────
# 리포트 4문장 (LLM) — 숫자는 표 안의 것만
# ─────────────────────────────────────────────
def _table_text(agg: dict, days: int) -> str:
    lines = [f"기간: 최근 {days}일 · 학생이 말한 문장 {agg['n']}개 (연습용 GEN 제외)"]
    lines.append("규칙별 (규칙 id · 이름 · 걸린 횟수 · 학생 수):")
    for r in agg["rules"][:10]:
        lines.append(f"- {r['rule_id']} {r['name']} · {r['count']}회 · 학생 {r['students']}명")
    lines.append("일별 (날짜 · 문장 수 · 맞은 문장 수):")
    for d in agg["days"]:
        lines.append(f"- {d['day']} · {d['n']}개 · 맞음 {d['ok_n']}개")
    lines.append("학생별 자주 걸린 규칙 (학생 · 규칙 이름 · 횟수):")
    for s in agg["students"]:
        lines.append(f"- 학생 {s['student']} · " + ", ".join(f"{t['name']} {t['count']}회" for t in s["top"]))
    return "\n".join(lines)


def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text or ""))


def report_sentences(agg: dict, days: int, backend: str | None = None) -> dict:
    """{'sentences': [...], 'dropped': [...], 'llm': {...}}. 표에 없는 숫자를 쓴 문장은 버린다 (지어낸 숫자 방지)."""
    if not agg["n"]:
        return {"sentences": [], "dropped": [], "llm": None, "note": "문장이 없어 리포트를 쓰지 않았어요"}
    table = _table_text(agg, days)
    prompt = PROMPT_FILE.read_text(encoding="utf-8").replace("{{table}}", table).replace("{{days}}", str(days))
    try:
        out = llm.generate_json(prompt, backend=backend)
    except llm.LLMError as e:
        return {"sentences": [], "dropped": [], "llm": None, "note": f"모델 호출 실패: {e}"}
    allowed = _numbers_in(table) | {str(days)}
    keys = ("most_missed", "improved", "next_unit", "cheer")
    sentences, dropped = [], []
    for k in keys:
        s = str(out.get(k) or "").strip()
        if not s:
            continue
        bad = _numbers_in(s) - allowed
        (dropped if bad else sentences).append({"key": k, "text": s, **({"bad_numbers": sorted(bad)} if bad else {})})
    return {"sentences": sentences, "dropped": dropped, "llm": out.get("_llm")}


# ─────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────
@router.get("/report")
def weekly_report(days: int = 7, source: str = "auto", sentences: bool = True):
    src = source if source in ("auto", "bq", "file") else "auto"
    if src == "auto":
        src = "bq" if bq_configured() else "file"
    if src == "bq" and not bq_configured():
        raise HTTPException(503, "BigQuery 설정 전 — .env 에 BQ_PROJECT 와 GOOGLE_APPLICATION_CREDENTIALS 를 넣고 tests/bq_upload.py 로 올리세요 (docs/plan-B/bigquery-report-plan.md)")
    file_rows = _file_rows(days)
    file_agg = aggregate_file(file_rows)
    if src == "bq":
        agg = aggregate_bq(days)
        check = {"file_n": file_agg["n"], "bq_n": agg["n"], "match": file_agg["n"] == agg["n"],
                 "rules_match": [(r["rule_id"], r["count"]) for r in agg["rules"]] == [(r["rule_id"], r["count"]) for r in file_agg["rules"]]}
    else:
        agg = file_agg
        check = {"file_n": file_agg["n"], "bq_n": None, "match": None, "rules_match": None}
    out = {"source": src, "days": days, "bq": {"configured": bq_configured(), "project": BQ_PROJECT or None, "table": f"{BQ_DATASET}.{BQ_TABLE}", "location": BQ_LOCATION},
           "check": check, **agg}
    out["report"] = report_sentences(agg, days) if sentences else None
    return out
