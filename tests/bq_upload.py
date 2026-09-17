"""sentence_log.jsonl → BigQuery 표 적재 (docs/plan-B/bigquery-report-plan.md 2-1).

    python -m tests.bq_upload            # 없는 log_id 만 추가 (중복 방지)
    python -m tests.bq_upload --replace  # 표를 비우고 전부 다시 적재
    python -m tests.bq_upload --dry      # BigQuery 에 안 붙고 스키마·행 수만 출력 (설정 확인용)

.env: BQ_PROJECT · BQ_DATASET(elem_english) · BQ_TABLE(sentence_log) · BQ_LOCATION(asia-northeast3) · GOOGLE_APPLICATION_CREDENTIALS
데이터셋·표가 없으면 만든다. 리허설·시연 뒤 한 번 돌리는 용도 — 서버가 문장마다 실시간 적재하지는 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import report                                     # noqa: E402  (.env 는 backend.config 가 읽는다)

LOG = ROOT / "data" / "student" / "sentence_log.jsonl"

# (이름, BigQuery 타입, 로그 필드 → 값 변환)
SCHEMA = [
    ("log_id", "STRING"), ("ts", "TIMESTAMP"), ("student", "STRING"), ("level", "INT64"), ("unit", "STRING"),
    ("text", "STRING"), ("source", "STRING"), ("spelled", "STRING"), ("rule_id", "STRING"), ("ok", "BOOL"),
    ("fixed", "STRING"), ("mission_ok", "BOOL"), ("mode", "STRING"), ("fallback_reason", "STRING"),
    ("top_score", "FLOAT64"), ("llm", "STRING"), ("llm_ms", "INT64"), ("total_ms", "INT64"), ("search_ms", "INT64"),
    ("llm_calls", "INT64"), ("failed", "STRING"),
]
INT = {n for n, t in SCHEMA if t == "INT64"}
FLT = {n for n, t in SCHEMA if t == "FLOAT64"}
BOOL = {n for n, t in SCHEMA if t == "BOOL"}


def read_log() -> list[dict]:
    rows = []
    if not LOG.exists():
        return rows
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        row = {}
        for name, _t in SCHEMA:
            v = r.get(name)
            if v is None or v == "":
                row[name] = None
            elif name == "ts":
                row[name] = datetime.fromisoformat(v).strftime("%Y-%m-%d %H:%M:%S") + "+09:00"   # 서버 로그는 한국 시각(naive)
            elif name in INT:
                row[name] = int(v)
            elif name in FLT:
                row[name] = float(v)
            elif name in BOOL:
                row[name] = bool(v)
            else:
                row[name] = str(v) if not isinstance(v, str) else v
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace", action="store_true", help="표를 비우고 전부 다시 적재")
    ap.add_argument("--dry", action="store_true", help="BigQuery 에 안 붙고 스키마·행 수만")
    args = ap.parse_args()

    rows = read_log()
    print(f"[bq_upload] {LOG.name}: {len(rows)}행 · 표 {report.BQ_DATASET}.{report.BQ_TABLE} · 프로젝트 {report.BQ_PROJECT or '(BQ_PROJECT 없음)'} · 리전 {report.BQ_LOCATION}")
    if args.dry:
        print("  스키마:", ", ".join(f"{n} {t}" for n, t in SCHEMA))
        if rows:
            print("  첫 행:", json.dumps(rows[0], ensure_ascii=False)[:300])
        return
    if not report.bq_configured():
        sys.exit("[bq_upload] .env 에 BQ_PROJECT 가 없어요. GOOGLE_APPLICATION_CREDENTIALS 도 같이 넣어 주세요.")
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("[bq_upload] 경고: GOOGLE_APPLICATION_CREDENTIALS 가 없어요 — gcloud 기본 인증(ADC)을 시도합니다")

    from google.cloud import bigquery                          # noqa: E402
    client = bigquery.Client(project=report.BQ_PROJECT, location=report.BQ_LOCATION)
    ds_id = f"{report.BQ_PROJECT}.{report.BQ_DATASET}"
    try:
        client.get_dataset(ds_id)
    except Exception:
        ds = bigquery.Dataset(ds_id); ds.location = report.BQ_LOCATION
        client.create_dataset(ds); print(f"[bq_upload] 데이터셋 만듦: {ds_id} ({report.BQ_LOCATION})")
    table_id = f"{ds_id}.{report.BQ_TABLE}"
    schema = [bigquery.SchemaField(n, t) for n, t in SCHEMA]
    try:
        table = client.get_table(table_id)
    except Exception:
        table = client.create_table(bigquery.Table(table_id, schema=schema)); print(f"[bq_upload] 표 만듦: {table_id}")

    if args.replace:
        client.query(f"TRUNCATE TABLE `{table_id}`").result()
        print("[bq_upload] 표 비움 (--replace)")
        existing: set[str] = set()
    else:
        existing = {r["log_id"] for r in client.query(f"SELECT log_id FROM `{table_id}`").result()}
    new_rows = [r for r in rows if r["log_id"] not in existing]
    print(f"[bq_upload] 이미 있음 {len(existing)} · 새로 올림 {len(new_rows)}")
    if not new_rows:
        return
    job = client.load_table_from_json(new_rows, table_id, job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_APPEND"))
    job.result()
    total = next(client.query(f"SELECT COUNT(*) AS n FROM `{table_id}`").result())["n"]
    print(f"[bq_upload] 완료 · 표 행 수 {total} (파일 {len(rows)}행)")


if __name__ == "__main__":
    main()
