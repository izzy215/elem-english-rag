# 초등 영어학습 · RAG 맞춤 복습 (조별 프로젝트)

기획: [docs/간단기획서.md](docs/간단기획서.md) · 한눈에 보기: [docs/elem-english-rag-overview.svg](docs/elem-english-rag-overview.svg)

## 폴더 구조

```
project/
├─ backend/
│   ├─ main.py        FastAPI 앱. 라우터를 모아 frontend/ 를 서빙
│   ├─ config.py      .env → settings  (키·모델은 항상 여기서 읽는다)
│   ├─ rag.py         (예정) A. 청킹 · 임베딩 · 검색 · 검수 경고 — RAG 담당
│   ├─ quiz.py        (예정) B. 문제 생성 + 오답 반영  — 팀장
│   ├─ explain.py     (예정) C. 오답 설명              — 팀장
│   ├─ tts.py         (예정) D. TTS 캐시 (sample 에서 복사) — TTS 담당
│   ├─ speak.py       (예정) E. 말하기 평가 (STT → 유사도) — TTS 담당
│   ├─ golden.py      (예정) data/golden/ 읽기 (levels · units · words · sentences) — TTS 담당
│   └─ prompts/       (예정) 프롬프트 텍스트 파일 — 코드 밖에서 수정
├─ frontend/          화면 하나 = HTML 하나 + js 하나 (팀장)
│   ├─ index.html     4.1 시작        js/start.js
│   ├─ units.html     4.2 Unit 목록   js/units.js
│   ├─ learn.html     4.3 학습        js/learn.js   (듣기 · 따라 말하기 포함)
│   ├─ quiz.html      4.4 문제 + 결과  js/quiz.js
│   ├─ explain.html   4.5 오답 설명   js/explain.js
│   ├─ css/app.css    공통 스타일
│   └─ js/common.js   API 호출(api) · 화면 간 상태(S.get/S.set, sessionStorage) · 상단바
├─ data/
│   ├─ golden/        데이터팀에서 받는 파일 (words.csv · sentences.csv · units.csv · chunks.jsonl · eval.csv)
│   │   └─ _sample/   납품 전 임시 데이터 20단어 (golden/ 에 진짜 파일이 생기면 자동으로 무시됨)
│   └─ student/       서버가 만드는 학생 로그 (quiz_log · wrong_words). git 제외
├─ docs/              기획서 · 그림 · 회의록 · 정확도 리포트
├─ tests/             평가셋 돌리는 스크립트 등
├─ .env.example       설정 항목 (복사해서 .env 로)
└─ requirements.txt
```

## 세팅

```bash
pip install -r project/requirements.txt
```
```bash
Copy-Item project/.env.example project/.env
```
`project/.env` 에 `GEMINI_API_KEY` 를 넣는다. 확인: `python project/backend/config.py`

## 실행

```bash
python -m uvicorn backend.main:app --app-dir project --reload --port 8000
```
→ http://localhost:8000  (`/api/health` 로 키·모델 확인)

## API (기획서 6절)

| 기능 | 경로 | 상태 |
|---|---|---|
| A. RAG 검색 (학습용) | `GET /api/rag/search?q=` | 스텁 |
| A'. RAG 검수 경고 | `POST /api/rag/check` | 스텁 |
| B. 문제 생성 | `POST /api/quiz` | 스텁 |
| C. 오답 설명 | `POST /api/explain` | 스텁 |
| D. TTS | `GET /api/tts/{id}` | 스텁 (sample 의 ensure_tts 이식) |
| E. 말하기 평가 | `POST /api/speak` | 스텁 (녹음 → STT → 원문 유사도 점수) |
| 학습 데이터 | `GET /api/levels`, `/api/units`, `/api/words` | 스텁 |

스텁 = 형식만 정해진 빈 응답. 각 담당이 채운다. **요청·응답 형식을 먼저 합의하고** 화면과 서버를 따로 만든다.

화면은 서버가 스텁이어도 돌아간다: `/quiz` 가 빈 응답이면 Unit 단어로 임시 문제를 만들고("임시 문제예요" 표시), `/tts` `/speak` `/explain` 이 비어 있으면 "준비 중"을 보여준다. 서버가 채워지면 화면 수정 없이 바뀐다.

## 화면 흐름

```
index.html ─▶ units.html ─▶ learn.html ─▶ quiz.html ─▶ explain.html
 학생·Level     Unit 선택     단어→문장    문제→결과     틀린 단어 설명 → 다시 풀기
```
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
| 리딩 + 화면 + AI API (문제 생성 · 오답 설명 · 프롬프트) | 팀장 | frontend/, backend/quiz.py, explain.py, prompts/ |
| TTS + 말하기 + 학습 데이터 API | 팀원 2 (TTS) | backend/tts.py, speak.py, golden.py |
| RAG + 검수 경고 + 정확도 측정 + 데이터팀 창구 | 팀원 3 (RAG) | backend/rag.py, tests/, data/golden/ |

골든 데이터셋 제작은 별도 데이터팀. 개발 3인은 받은 파일을 읽어 쓰는 쪽만.
