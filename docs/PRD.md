# PRD v1.0 — 초등 영어학습 · RAG 맞춤 복습

작성 2026-09-04 · 팀장 · 상태: **1차 (개발 착수용)**
근거 문서: [간단기획서 v0.2](간단기획서.md) · 데이터 파이프라인: rag-data-flow.png

이 문서의 목적은 하나다. **3명이 서로 기다리지 않고 동시에 개발을 시작할 수 있게** 화면·API·데이터 형식을 고정한다.
"미정"으로 표시된 항목은 착수를 막지 않는 선에서 기본값을 정해 두었고, 바뀌면 이 문서를 고친다.

---

## 1. 제품 정의

| 항목 | 내용 |
|---|---|
| 한 줄 | 초등학생이 Level·Unit을 골라 단어·문장을 학습하고 AI 문제를 풀면, 오답을 기록해 두었다가 RAG가 교재에서 근거를 찾아 **그 학생에게 맞는 문제와 설명**을 다시 만들어 주는 서비스 |
| 핵심 루프 | 학습 → 오답 기록 → RAG 교재 검색 → 맞춤 문제·오답 설명 → 다시 학습 |
| 1차 사용자 | 초등 3~6학년 학생 (로그인 없음, 이름 드롭다운) |
| 부 사용자 | 관리자(선생님) — 소스 등록 시 RAG 검수 경고, 정확도 대시보드 |
| 발표 핵심 문장 | "같은 Unit인데 학생 A와 B가 받는 문제가 다르다" + "검색 정확도 62% → 84%" |

## 2. 범위 (기획서 4절 확정본)

○ 1차: Level 선택 · Unit 선택 · 단어 학습 · 문장 학습 · AI 문제 생성(오답 반영) · RAG 검색(학습용) · RAG 검수 경고(등록용) · 오답 설명 · 듣기(TTS) · 말하기 평가(STT 유사도)
✕ 제외: 로그인 · 개인별 복습 화면 · 스토리 생성 · XP/배지/랭킹 · 음소 단위 발음 채점

## 3. 사용자 시나리오 (데모 60초)

1. 시작 화면에서 "학생 A" 선택 → Level 2
2. Unit 3 "Animals" 선택
3. 단어 카드 5개: rabbit / 토끼 / The rabbit can jump. — 듣기 버튼, 따라 말하기 → 점수 82
4. 문장 카드 3개 → 문제 풀기
5. 문제 3개 중 rabbit 문제 틀림 → 즉시 채점
6. 오답 설명: "rabbit은 토끼예요. 교재 12쪽: The rabbit can jump." + 출처 표시
7. [다시 풀기] → rabbit이 첫 문제로 출제됨. "학생 B"로 바꾸면 다른 문제
8. 관리자 화면: 정확도 그래프

## 4. 화면 명세 (팀장)

공통: 상단에 학생 이름 · Level · Unit 표시. 모든 화면은 `frontend/index.html` 하나 안의 `.screen` 전환 (sample 방식). 모바일 폭(360px) 우선.

### 4.1 시작
| 요소 | 동작 | API |
|---|---|---|
| 학생 드롭다운 | 학생 A / 학생 B (고정 2명) | — |
| Level 카드 3개 | 클릭 → Unit 목록 | `GET /api/levels` |

### 4.2 Unit 목록
| 요소 | 동작 | API |
|---|---|---|
| Unit 카드 (제목 · 단어 수 · 진행률) | 클릭 → 학습 | `GET /api/units?level=` |
| 진행률 | 학습한 단어 수 / 전체 | `GET /api/progress?student=&level=&unit=` |

### 4.3 학습
| 요소 | 동작 | API |
|---|---|---|
| 단어 카드 (word · meaning · example · 출처 쪽) | 좌우 이동 | `GET /api/words?level=&unit=` |
| 🔊 듣기 | 음원 재생 (캐시) | `GET /api/tts/{item_id}` |
| 🎙 따라 말하기 | 녹음 3초 → 점수 표시 | `POST /api/speak` |
| 문장 카드 (sentence · meaning) | 단어 끝나면 이어서 | `GET /api/sentences?level=&unit=` |
| [문제 풀기] | → 4.4 | — |

### 4.4 문제 풀기
| 요소 | 동작 | API |
|---|---|---|
| 문제 3개 (기본값, 최대 5) | 객관식 4지선다 (1차 기본). 빈칸은 미정 | `POST /api/quiz` |
| 보기 클릭 | 즉시 채점, 정답/오답 표시 | `POST /api/answer` |
| 완료 | 틀린 문제 있으면 → 4.5, 없으면 → 4.2 | — |

### 4.5 오답 설명
| 요소 | 동작 | API |
|---|---|---|
| 틀린 문제별 카드 | 설명 + 출처("교재 N쪽" + 원문 조각) | `POST /api/explain` |
| 🔊 듣기 | 해당 단어 음원 | `GET /api/tts/{item_id}` |
| [다시 풀기] | → 4.4 (오답 반영된 새 문제) | `POST /api/quiz` |

### 4.6 관리자 (△ 최소)
| 요소 | 동작 | API |
|---|---|---|
| 소스 등록 폼 (sample 재사용) | 등록 시 경고 한 줄 표시 | `POST /api/rag/check` |
| 정확도 카드 | 평가셋 기준 hit@3, 개선 전후 | `GET /api/rag/eval` |

## 5. API 명세

베이스 `/api`. 요청·응답은 JSON. 오류는 `{"detail": "메시지"}` + 4xx/5xx. 아래 형식은 **계약**이며 바꾸려면 세 사람 합의.

### 5.1 학습 데이터 (TTS 담당 · `golden.py`)

```
GET /levels
→ [{"level":1,"label":"Level 1 · 3~4학년","units":4}]

GET /units?level=2
→ [{"unit":"U3","title":"Animals","words":12,"sentences":6}]

GET /words?level=2&unit=U3
→ [{"id":"w-0031","word":"rabbit","meaning":"토끼","example":"The rabbit can jump.","source_page":12}]

GET /sentences?level=2&unit=U3
→ [{"id":"s-0012","sentence":"The rabbit can jump.","meaning":"토끼는 뛸 수 있어요.","source_page":12}]

GET /progress?student=A&level=2&unit=U3
→ {"learned":5,"total":12,"quiz_taken":2,"wrong_words":["rabbit","jump"]}
```

### 5.2 TTS · 말하기 (TTS 담당 · `tts.py`, `speak.py`)

```
GET /tts/{item_id}            item_id = 단어 id 또는 문장 id
→ audio/wav (24kHz mono). 캐시: audio_cache/{item_id}.wav
   없으면 Gemini TTS로 생성 후 저장. 원문은 golden에서 id로 찾는다.

POST /speak
{"student":"A","item_id":"s-0012","audio_base64":"...","mime":"audio/webm"}
→ {"heard":"the rabbit can jump","expected":"The rabbit can jump.","score":82,"passed":true}
   score = 정규화(소문자·구두점 제거) 후 단어 단위 유사도 0~100. passed = score ≥ 70 (미정, 기본값 70)
   STT는 Gemini 멀티모달(오디오 입력). 실패 시 {"heard":"", "score":0, "error":"..."}
```

### 5.3 RAG (RAG 담당 · `rag.py`)

```
GET /rag/search?q=rabbit&level=2&k=3
→ {"query":"rabbit","chunks":[{"id":"c-0102","text":"rabbit은 초등 영어 기본 어휘이며 뜻은 토끼이다. 예문: The rabbit can jump.","level":2,"unit":"U3","source_page":12,"score":0.91}]}
   level 은 선택(없으면 전체). 정렬은 score 내림차순.

POST /rag/check
{"text":"The giraffe is eating leaves.","level":2}
→ {"ok":false,"warnings":["범위 밖 단어: giraffe","유사 문장 87%: The rabbit is eating grass. (U3)"]}
   ok = warnings 비어 있음. 범위 밖 판단 = golden words 목록에 없는 단어. 유사 문장 = 검색 score ≥ 0.85

GET /rag/eval
→ {"n":30,"hit_at_3":0.84,"hit_at_1":0.63,"runs":[{"label":"글자 500 청킹","hit_at_3":0.62},{"label":"문장 단위 청킹","hit_at_3":0.84}]}
   eval.csv 를 돌린 결과. runs 는 tests/ 에서 기록한 실험 이력.
```

### 5.4 문제 · 오답 (팀장 · `quiz.py`, `explain.py`)

```
POST /quiz
{"student":"A","level":2,"unit":"U3","count":3}
→ {"quiz_id":"q-20260904-001","questions":[
     {"id":"q1","type":"choice","word_id":"w-0031","prompt":"'토끼'를 영어로?","choices":["rabbit","cat","dog","bird"],"answer":0,"source_chunk_id":"c-0102"}]}
   생성 규칙: (1) 이 학생의 wrong_words 를 count 의 절반 이상 포함 (2) 나머지는 Unit 단어 중 무작위
   (3) 각 문제는 RAG 조각 1개를 근거로 (4) Gemini 응답은 JSON 스키마 강제, 파싱 실패 시 1회 재시도

POST /answer
{"student":"A","quiz_id":"q-20260904-001","question_id":"q1","choice":2}
→ {"correct":false,"answer":0}
   오답이면 student DB 의 wrong_words 에 word 추가, quiz_log 에 기록

POST /explain
{"student":"A","quiz_id":"q-20260904-001","question_id":"q1"}
→ {"explanation":"rabbit은 '토끼'예요. 귀가 길고 깡충깡충 뛰는 동물이에요.","source":{"chunk_id":"c-0102","page":12,"text":"The rabbit can jump."}}
   규칙: 초등 3학년이 읽을 수 있는 문장 2~3개, 반드시 source 포함, 조각에 없는 내용은 만들지 않음
```

### 5.5 공통

```
GET /health → {"ok":true,"api_key":true,"model":"gemini-3.6-flash","golden_files":["words.csv", ...]}
```

## 6. 데이터 명세

### 6.1 골든 데이터셋 (데이터팀 → `data/golden/`)

| 파일 | 컬럼 | 비고 |
|---|---|---|
| `words.csv` | id, level, unit, word, meaning, example, source_page | id 는 `w-0001` 형식, UTF-8 |
| `sentences.csv` | id, level, unit, sentence, meaning, source_page | id 는 `s-0001` |
| `chunks.jsonl` | id, text, level, unit, source_page, word_ids | 한 줄 = 조각 1개. **RAG 검색 대상** |
| `units.csv` | level, unit, title, order | Unit 목록·순서 |
| `eval.csv` | question, expected_chunk_id, note | 30문항 이상. RAG 정확도 측정용 |

1차 납품 최소치: Level 2의 Unit 2개, 단어 40개, 문장 20개, chunks 60개, eval 30문항.
**납품 전까지** 개발팀은 `data/golden/_sample/` 에 같은 형식의 임시 데이터 20단어를 두고 개발한다 (RAG 담당이 1주차 2일까지 작성).

### 6.2 학생 DB (`data/student/`, JSON → 여유 시 BigQuery)

```
students.json   [{"id":"A","name":"학생 A","level":2}]
quiz_log.jsonl  {"ts":"2026-09-10T14:02:11","student":"A","quiz_id":"q-..","question_id":"q1","word_id":"w-0031","word":"rabbit","correct":false}
wrong_words.json {"A":{"rabbit":{"count":2,"last":"2026-09-10"},"jump":{"count":1,"last":"2026-09-09"}}}
progress.json    {"A":{"2/U3":{"learned_word_ids":["w-0031",...],"quiz_taken":2}}}
```

오답 반영 우선순위 = count 내림차순, 같으면 last 최신순.

### 6.3 RAG 저장소 (`data/chroma/` · Chroma · RAG 담당)

```
data/golden/chunks.jsonl  ──임베딩(조각당 1회)──▶  data/chroma/   ──검색──▶  /rag/search
```

| 항목 | 결정 |
|---|---|
| 벡터 DB | **Chroma** (`chromadb`, 로컬 폴더 저장). 수업에서 다른 것을 쓰면 rag.py 안에서만 교체 |
| 컬렉션 | `chunks` 하나. 문서 = chunk 1개, id = chunks.jsonl 의 id |
| 메타데이터 | level, unit, source_page, word_ids — `/rag/search?level=` 필터에 사용 |
| 임베딩 | Gemini Embedding API. **chunks.jsonl 이 바뀔 때만** 다시 생성 (`tests/build_index.py` 같은 스크립트로) |
| 생성 시점 | 서버 시작 시 `data/chroma/` 가 없으면 자동 생성, 있으면 읽기만 |
| Git | `data/chroma/` 는 제외. 각자 chunks.jsonl 로 다시 만들 수 있음 |
| 검수용 | `/rag/check` 도 같은 컬렉션을 검색 (유사 문장 = score ≥ 0.85) |

(2026-09-04 추가: FAISS → Chroma)

## 7. 프롬프트 규칙 (`backend/prompts/*.txt`)

| 파일 | 역할 | 반드시 포함 |
|---|---|---|
| `quiz.txt` | 문제 생성 | Unit 단어 목록, 우선 단어(오답), RAG 조각, 출력 JSON 스키마, "보기는 같은 Unit 단어로" |
| `explain.txt` | 오답 설명 | 틀린 문제, 학생 답, RAG 조각, "초등 3학년 어휘로 2~3문장", "조각에 없는 내용 금지", 출처 표기 형식 |
| `check.txt` | 검수 경고 (선택) | RAG 결과를 한 줄 경고로 요약 |

프롬프트는 코드 밖 텍스트 파일로 두고, `{{변수}}` 자리에 값을 채운다. 수정 후 서버 재시작 없이 반영(파일을 매 호출 읽음).

## 8. 비기능 요구사항

| 항목 | 기준 |
|---|---|
| 응답 시간 | 화면 전환 즉시. TTS 첫 재생 ≤ 10초(이후 캐시 즉시). 문제 생성 ≤ 30초, "생각 중" 표시 |
| 비용 | 무료 티어 내. TTS·임베딩은 1회 생성 후 캐시 |
| 키 관리 | `.env` 만. 코드·저장소에 키 금지 |
| 브라우저 | Chrome 최신. 마이크는 localhost 에서만 보장 |
| 데이터 | 학생 실명 없음(학생 A/B). 녹음 파일은 채점 후 저장하지 않음 |

## 9. 성공 지표

| 지표 | 목표 | 측정 |
|---|---|---|
| RAG hit@3 | ≥ 80% | eval.csv 30문항, `/rag/eval` |
| 오답 반영 | 다시 풀기에서 wrong_words 가 첫 문제 | 데모 시나리오 7번 |
| 문제 생성 성공률 | JSON 파싱 성공 ≥ 95% | quiz_log |
| 말하기 채점 | 정상 발화 시 score ≥ 70 | 팀원 5회 테스트 |

## 10. 마일스톤

| 일차 | 완료 기준 |
|---|---|
| 2일 | 3명 모두 서버 실행 · `.env` · `_sample` 임시 데이터로 `/words` 응답 |
| 5일 | 화면 4.1~4.3 동작(임시 데이터) · TTS 재생 · RAG 검색 기본 동작 |
| 8일 | 골든 데이터 교체 · `/quiz` `/answer` `/explain` 동작 · hit@3 1차 측정 |
| 11일 | 오답 반영 · 청킹 개선 2차 측정 · 말하기 평가 · 검수 경고 |
| 13일 | **기능 동결.** 버그만 · 발표 자료 · 데모 리허설 |
| 15일 | 발표 |

## 11. 미정 항목 (기본값으로 착수)

| 항목 | 기본값 | 결정 시점 |
|---|---|---|
| 문제 유형 | 객관식 4지선다만 | 8일차 |
| 말하기 통과 점수 | 70 | 11일차 |
| Level ↔ 학년 | 1=3~4, 2=5, 3=6 | 데이터팀 납품 시 |
| 골든 파일 컬럼명 | 6.1 표 | 데이터팀 협의 (1주차) |
| BigQuery 사용 | 안 함 (JSON) | 11일차 여유 시 |
| 관리자 화면 범위 | 등록 폼 + 정확도 카드 | 8일차 |
