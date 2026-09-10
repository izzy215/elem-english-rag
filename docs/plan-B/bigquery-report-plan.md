# BigQuery 주간 리포트 — 작업 지시서 (2주차 · 여유 시)

작성 2026-09-10 · 팀장(PM 세션) · 실행: 작업 세션 또는 팀원 · 상태: **미착수, GCP 프로젝트 결정 대기**
근거: PRD 11장 "BigQuery 주간 리포트 — 11일차 여유 시. sentence_log → 집계 → Gemini 리포트 문장 (관리자 패널)"

## 0. 한 줄

지금 관리자 화면이 서버 파일(`data/student/sentence_log.jsonl`)로 하는 집계를 **BigQuery SQL 로도 뽑아** 같은 숫자를 보여주고, 그 집계로 **주간 리포트 문장**을 LLM 이 쓰게 한다. "데이터가 쌓이면 이렇게 분석한다" 를 발표에서 보여주는 용도. 서비스 동작(/fix, 오답노트)은 건드리지 않는다.

## 1. 준비 (팀장 결정 사항)

| 항목 | 내용 |
|---|---|
| GCP 프로젝트 | 팀장 계정에 새로 만들거나 기존 것 사용. 프로젝트 id 를 `.env` 에 `BQ_PROJECT=` 로 |
| 데이터셋 | `elem_english` (리전 asia-northeast3). 표 1개 `sentence_log` |
| 인증 | 서비스 계정(BigQuery 데이터 편집자 + 작업 사용자) 키 json → `.env` 에 `GOOGLE_APPLICATION_CREDENTIALS=경로`. 키 파일은 git 밖 |
| 비용 | 무료 한도 안 (저장 10GB · 조회 월 1TB). 우리 로그는 수천 행 |
| 패키지 | `google-cloud-bigquery>=3.0` (requirements.txt 에 한 줄) |

## 2. 만들 것 (순서대로)

### 2-1. 올리기 — `tests/bq_upload.py` (팀장 소유)
- `sentence_log.jsonl` 을 읽어 BigQuery 표 `sentence_log` 에 적재. 스키마는 로그 필드 그대로:
  `log_id STRING, ts TIMESTAMP, student STRING, level INT64, unit STRING, text STRING, source STRING, spelled STRING, rule_id STRING, ok BOOL, fixed STRING, mission_ok BOOL, mode STRING, fallback_reason STRING, top_score FLOAT64, llm STRING, llm_ms INT64, total_ms INT64, search_ms INT64, llm_calls INT64, failed STRING`
- `log_id` 로 중복 방지 (이미 있는 행은 건너뜀). `--replace` 옵션이면 표를 비우고 다시 적재.
- 리허설·시연 뒤 한 번 돌리는 방식이면 충분. 서버가 문장마다 실시간 적재하는 건 하지 않는다 (키·네트워크 의존이 서비스에 들어오지 않게).

### 2-2. 집계 — `backend/report.py` (팀장 소유, 라우터 `/admin/report`)
- `GET /admin/report?days=7` → BigQuery SQL 3개를 돌려 반환:
  1. 규칙별 걸린 횟수·학생 수 (`rule_id`, `COUNT(*)`, `COUNT(DISTINCT student)`) — 관리자 문장 로그 표와 같은 정의
  2. 일별 문장 수·맞음 비율 (`DATE(ts)`)
  3. 학생별 상위 3 규칙
- BigQuery 설정이 없으면(.env 에 `BQ_PROJECT` 없음) 503 과 안내 문구. 관리자 화면은 그때 패널을 "설정 전" 으로 둔다.
- 같은 기간의 파일 집계(`/admin/log`)와 숫자가 맞는지 확인하는 항목을 응답에 넣는다 (`file_n` vs `bq_n`).

### 2-3. 리포트 문장 — 같은 `report.py`
- 위 집계를 표로 만들어 `llm.generate_json()` 에 넣고 "선생님께 보내는 주간 리포트 4문장" (가장 많이 틀린 규칙, 나아진 학생, 다음 주 권장 유닛, 한 줄 격려) 을 받는다. 프롬프트는 `backend/prompts/report.txt`.
- LLM 이 지어낼 수 있는 숫자는 프롬프트에 넣은 표 안의 것만 쓰라고 못 박고, 응답의 숫자가 표에 없으면 그 문장은 버린다.

### 2-4. 관리자 화면 — `frontend/admin.html`, `frontend/js/admin.js` (팀장 소유)
- 새 패널 "주간 리포트 (BigQuery)": 규칙별 표 · 일별 막대 · 리포트 4문장 · "파일 집계와 일치" 표시.
- 설정 전이면 "BigQuery 설정 전 — docs/plan-B/bigquery-report-plan.md" 한 줄.

## 3. 완료 기준
- [ ] `python -m tests.bq_upload` 뒤 BigQuery 콘솔에서 행 수 = sentence_log.jsonl 행 수
- [ ] `/admin/report?days=7` 의 규칙별 횟수가 `/admin/log?days=7` 과 같음
- [ ] 관리자 화면에 리포트 4문장 표시, 숫자가 표와 일치
- [ ] PRD 3.7 표에 "주간 리포트 | GET /admin/report" 행, README API 표에 한 줄

## 4. 하지 않는 것
- 실시간 적재, 학생 화면 변경, 개인정보 컬럼 추가 (학생 id 는 A/B 같은 별칭 그대로)
- BigQuery 가 안 되면 기존 파일 집계가 그대로 서비스 — 리포트 패널만 비어 있음
