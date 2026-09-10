# 초등 영어학습 · RAG 맞춤 복습 (조별 프로젝트)

기획(확정 B안): [docs/plan-B/간단기획서.md](docs/plan-B/간단기획서.md) · PRD: [docs/plan-B/PRD.md](docs/plan-B/PRD.md) · 목업: [docs/plan-B/mockup.html](docs/plan-B/mockup.html) · 흐름도: [docs/common/architecture-flow.svg](docs/common/architecture-flow.svg)

## 폴더 구조

```
project/
├─ backend/
│   ├─ main.py        FastAPI 앱. 라우터를 모아 frontend/ 를 서빙
│   ├─ config.py      .env → settings  (키·모델은 항상 여기서 읽는다)
│   ├─ rag.py         ✓ Chroma 검색 → /rag/search · /rag/eval (search_rules, R-01 어휘 안전망) — RAG 담당
│   ├─ indexing.py    ✓ 색인 생성·검증 (`python -m backend.indexing --rebuild` / `--validate-only`) — RAG 담당
│   ├─ embedding.py   ✓ gemini-embedding-001 (3072차원) 임베딩 — RAG 담당
│   ├─ tutor.py       ✓ /fix 내 문장 고쳐주기 (RAG 검색 + 후보 규칙 + LLM + 서버 검증 · 철자 · 규칙 밖) — 팀장
│   ├─ llm.py         ✓ LLM 스위치 (LLM_BACKEND=gemini | claude | 엔드포인트 이름, 실패 시 gemini 폴백) — 팀장
│   ├─ ask.py         ✓ /ask 물어보기 챗 (FAQ 로컬 매칭 + LLM, RAG 연결 예정) — TTS 팀원
│   ├─ student.py     ✓ 오답노트 읽기 /notebook (쓰기는 tutor.py · drill.py 가 함) — 팀장
│   ├─ drill.py       ✓ 규칙 연습 4지선다 · /drill · /drill/answer — 팀장
│   ├─ admin.py       ✓ 관리자 /admin/golden · /admin/log (BigQuery 리포트는 미착수) — 팀장
│   ├─ tts.py         ✓ TTS 캐시 · speak.py ✓ STT(로컬 Whisper) + 유사도 (+ 발음 파형 실험) — TTS 팀원
│   ├─ whisper_server.py  ✓ 강의실 GPU 서버용 Whisper 서버 (없으면 로컬 CPU 폴백) — TTS 팀원
│   ├─ golden.py      ✓ data/golden/ 읽기 (levels · units · words · patterns · rules · faq · errors) — TTS 팀원
│   ├─ pronounce.py   발음 파형 비교 실험 (참고용) — TTS 팀원
│   ├─ quiz.py · explain.py   A안 잔재 (라우터만 남음)
│   └─ prompts/       fix_fallback.txt 하나 ({{mission}} {{hint_words}} {{all_rules}} {{sentence}}) — 코드 밖에서 수정
├─ frontend/          화면 하나 = HTML 하나 + js 하나 (팀장)
│   ├─ index.html     시작          js/start.js
│   ├─ units.html     Unit 목록     js/units.js
│   ├─ learn.html     표현 익히기   js/learn.js
│   ├─ tutor.html     내 문장 고치기 js/tutor.js  (핵심 · 근거 박스 두 겹 · 다시 고쳐줘)
│   ├─ shadow.html    따라 말하기   js/shadow.js  (TTS 팀원)
│   ├─ notebook.html  오답노트      js/notebook.js
│   ├─ drill.html     규칙 연습     js/drill.js
│   ├─ admin.html     관리자        js/admin.js
│   ├─ archive-A/     A안 화면 보관 (quiz · explain · fix)
│   ├─ css/app.css    공통 스타일
│   └─ js/common.js   API 호출(api) · 화면 간 상태(S.get/S.set, sessionStorage) · 상단바 · 🙋 챗 시트
├─ data/
│   ├─ golden/        데이터팀에서 받는 파일 (rules.jsonl · faq.jsonl · errors.jsonl · eval.csv · units · patterns · words)
│   │   ├─ _sample-B/ B안 컬럼 정의 + 예시 (README 에 해설) ← 데이터팀 기준
│   │   └─ _sample/   A안 임시 단어 20개 (구)
│   ├─ chroma/        규칙 색인 (manifest.json 의 active_collection). git 제외
│   ├─ rag_eval/      retrieval_eval_latest.json · fix_compare_*.json/.md. git 제외
│   └─ student/       서버가 만드는 학생 로그 (sentence_log.jsonl · notebook.json · drill_log.jsonl). git 제외
├─ docs/              기획 문서 — README.md 에 안내
│   ├─ plan-B/        ✓ 확정 — 내 문장 고쳐주기 튜터 (기획서 · PRD · 목업 · 데이터 계획 · 다이어그램)
│   ├─ archive/plan-A/  보관 — 단어 4지선다 안
│   └─ common/        아키텍처 흐름도 · 데이터 파이프라인 원본 그림
├─ tests/             평가셋 돌리는 스크립트 등
├─ .env.example       설정 항목 (복사해서 .env 로)
└─ requirements.txt
```

## 세팅 (처음 한 번)

가상환경(`.venv`)은 Git에 없다. **각자 자기 컴퓨터에서 만든다.** 아래는 저장소를 받은 폴더 안에서 실행.
Python 3.11 이상 (`python --version` 또는 `python3 --version` 으로 확인).

### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

### Mac · Linux (터미널)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

그다음 `.env` 를 열어 `GEMINI_API_KEY=` 뒤에 자기 키를 넣는다 (https://aistudio.google.com/apikey 에서 무료 발급).
확인: `python backend/config.py` → "API 키: 설정됨" 이면 끝.

| | Windows | Mac · Linux |
|---|---|---|
| 파이썬 명령 | `python` | `python3` (설치에 따라 `python` 도 됨) |
| 가상환경 켜기 | `.venv\Scripts\activate` | `source .venv/bin/activate` |
| 가상환경 끄기 | `deactivate` | `deactivate` |
| 파이썬 실행 파일 위치 | `.venv\Scripts\python.exe` | `.venv/bin/python` |

가상환경이 켜지면 프롬프트 앞에 `(.venv)` 가 붙는다. 터미널을 새로 열 때마다 켜야 한다 (VS Code 는 자동으로 켜 줌).
PowerShell 에서 `activate` 가 "스크립트 실행이 차단" 되면 한 번만: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 실행

가상환경을 켠 상태에서, 저장소 폴더 안에서:
```bash
uvicorn backend.main:app --reload --port 8000
```
→ http://localhost:8000  (`/api/health` 로 키·모델 확인)

가상환경을 안 켰거나 `uvicorn` 을 못 찾으면 `python -m uvicorn backend.main:app --reload --port 8000` (Mac은 `python3 -m ...`).
`.env` 를 바꾸면 서버를 다시 켠다.

## 자주 막히는 것

| 증상 | 원인 · 해결 |
|---|---|
| `uvicorn: command not found` | 가상환경이 안 켜짐 → activate 먼저 |
| `ModuleNotFoundError: backend` | 저장소 폴더 밖에서 실행함 → `cd` 로 README 가 있는 폴더로 |
| `GEMINI_API_KEY 없음` | `.env` 를 안 만들었거나 키를 안 넣음 |
| VS Code 가 패키지를 못 찾음 | 오른쪽 아래 인터프리터를 `.venv` 것으로 선택 (Windows: `.venv\Scripts\python.exe`, Mac: `.venv/bin/python`) |
| Mac에서 `python` 이 2.x | `python3` 사용 |

## API (PRD-B 4절)

| 기능 | 경로 | 담당 | 상태 |
|---|---|---|---|
| RAG 검색 · 평가 | `GET /api/rag/search?q=&level=&k=` · `GET /api/rag/eval` | RAG | **완성** |
| 내 문장 고쳐주기 | `POST /api/fix` | 팀장 | **완성** |
| 물어보기 챗 | `POST /api/ask` | TTS 팀원 | **완성** (FAQ 매칭 + LLM, RAG 연결 예정) |
| 오답노트 | `GET /api/notebook` | 팀장 | **완성** |
| 규칙 연습 | `GET /api/drill` · `POST /api/drill/answer` | 팀장 | **완성** |
| 관리자 | `GET /api/admin/golden` · `GET /api/admin/log?days=` | 팀장 | **완성** |
| TTS · STT | `GET /api/tts/{id}` · `POST /api/speak` | TTS 팀원 | **완성** |
| 학습 데이터 | `GET /api/levels` `/units` `/words` `/patterns` | TTS 팀원 | **완성** (납품본 Level 3 · Unit01~20) |

backend 의 quiz.py · explain.py 는 A안 잔재로 라우터만 남아 있다 (화면은 frontend/archive-A/). B 기능은 tutor.py · ask.py · drill.py 가 맡는다.

스텁 = 형식만 정해진 빈 응답. 각 담당이 채운다. **요청·응답 형식을 먼저 합의하고** 화면과 서버를 따로 만든다.

화면은 서버가 일부 비어 있어도 돌아간다: `/fix` 는 검색이 실패하면 규칙 전부를 넣는 폴백 모드(`mode:"fallback"`)로 진단하고, `/tts` `/speak` 가 비어 있으면 "준비 중"을 보여준다.

## 화면 흐름 (B안 · 목업 docs/plan-B/mockup.html)

```
index.html ─▶ units.html ─▶ learn.html ─▶ tutor.html ─▶ notebook.html ─▶ drill.html
 학생·Level     미션 선택    표현 익히기    내 문장 고치기   오답노트(문법)    규칙 연습
                              └▶ shadow.html 따라 말하기          Unit 안 5화면: 🙋 물어보기 챗 시트
admin.html  관리자 (골든 데이터 · RAG 정확도 · STT 정확도 자리 · 학생 문장 로그 · 못 짚은 문장)
```
frontend 는 B안 화면으로 교체 완료 (A안 quiz · explain 은 frontend/archive-A/ 보관).
화면 사이 값(학생 · Level · Unit · 단어 목록 · 문제 결과)은 `js/common.js` 의 `S.set()` 으로 저장하고 다음 화면에서 `S.get()` 으로 읽는다.
새 화면을 만들 때: HTML 복사 → `<main>` 만 바꾸기 → `js/이름.js` 만들고 맨 아래 `<script>` 두 줄 유지.

## 규칙

- 키·모델명은 코드에 쓰지 않는다. `from backend.config import settings`
- `.env` 공유 금지. `data/student/` 와 `audio_cache/` 는 git 에 올리지 않는다.
- 프롬프트는 `backend/prompts/*.txt` 로 분리한다 (코드 안 건드리고 수정 가능).
- 기능 하나 = 서버 파일 하나 + API 하나 + `app.js` 함수 하나.
- 13일차 이후 새 기능 금지, 버그만 고친다.

## 담당

| 역할 | 담당 | 파일 |
|---|---|---|
| 리딩 + 화면 + `/fix` 파이프라인(프롬프트 · 서버 검증 · 재확인) + LLM 스위치 + 규칙 연습 + 오답노트 데이터 + 관리자 (BigQuery 주간 리포트는 미착수) | 팀장 | frontend/, backend/tutor.py, llm.py, drill.py, student.py, admin.py, prompts/ |
| 따라 말하기 · 물어보기 챗 · TTS/STT(로컬 Whisper) | 팀원 2 (TTS) | frontend(따라 말하기 · 챗 시트), backend/ask.py, tts.py, speak.py, whisper_server.py, golden.py |
| RAG 검색 · 색인 · 임베딩 모델 비교 · 평가 · 데이터팀 창구 | 팀원 3 (RAG) | backend/rag.py, indexing.py, embedding.py, tests/eval_rag.py, data/golden/ |

골든 데이터셋 제작은 별도 데이터팀. 개발 3인은 받은 파일을 읽어 쓰는 쪽만.
