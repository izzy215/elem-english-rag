# PRD-B v0.1 — 내 문장 고쳐주기 튜터

작성 2026-09-06 · 팀장 · 상태: **v1.0 확정 (2026-09-07)** · A안은 ../archive/plan-A/
근거: [간단기획서-B](간단기획서.md) · [mockup.html](mockup.html) · [data-pipeline-plan-B](data-pipeline-plan.md)

목적: 3명이 동시에 착수할 수 있게 **화면 · API 계약 · 데이터 형식**을 고정한다. 미정은 기본값으로 착수.

---

## 1. 제품 정의

| 항목 | 내용 |
|---|---|
| 한 줄 | 학생이 말하거나 쓴 영어 문장을, RAG가 우리 규칙 조각에서 관련 규칙을 찾아 AI가 근거와 함께 고쳐주는 튜터 |
| 핵심 루프 | 표현 익히기 → 내 문장 → RAG 규칙 검색 → 고쳐주기 → 오답노트(문법) → 규칙 연습 |
| RAG 입구 | ① 문장 → 규칙 (`/fix`) ② 질문 → 설명 조각 (`/ask`) |
| DB 조회 (RAG 아님) | 오답노트 · 패턴 · 단어 · 규칙 연습 문제 |
| RAG의 역할 | **깔때기**(다양한 질문·라벨 없는 문장 → 올바른 조각) + **목줄**(조각 밖 내용 생성 금지). 지식 확장이 아님 → [docs/README 공통 전제](../README.md) |
| 발표 핵심 | "🎙 → 검색 점수 0.91 → went + 근거" / "문장→규칙 hit@3 87%" / "DB와 RAG를 구분해 썼다" |

## 2. 사용자 시나리오 (데모 60초)

1. 학생 A → Level 2 → U3 "동물원에서 본 것" (배지: 헷갈리는 규칙 2)
2. 표현 익히기: 패턴 "I saw a rabbit." 듣기
3. 내 문장: 🎙 "I go to the zoo yesterday" → 들린 문장 표시
4. 고쳐줘 → ① 받기 ② RAG 검색 ③ AI 설명 순서로 표시
5. 결과: 헷갈린 규칙 과거시제 · ~~go~~ went · 설명 2문장 · 근거 R-01 (점수 0.91, 2위 관사 0.42)
6. 더 물어보기 "왜 went예요?" → 근거 붙은 답
7. 오답노트: 과거시제 3회 · 내 문장/고친 문장 · [연습하기] → 2문제
8. 학생 B로 바꾸면 오답노트 비어 있음 · 관리자: 정확도 그래프

## 3. 화면 명세 (팀장)

공통: 화면별 HTML + JS, 상태는 `common.js` 의 `S.get/S.set`. 모바일 375px 우선.

### 3.1 시작 `index.html`
| 요소 | 동작 | API |
|---|---|---|
| 학생 드롭다운 | A / B | — |
| Level 카드 | Level 2만 활성 | `GET /levels` |
| 📒 오답노트 버튼 | 헷갈리는 규칙 수 표시 → 오답노트 | `GET /notebook?student=` |

### 3.2 Unit 목록 `units.html`
| 요소 | 동작 | API |
|---|---|---|
| Unit 카드 (미션 이름) | → 표현 익히기 | `GET /units?level=` |
| 배지 | 이 Unit 규칙 중 헷갈리는 것 수 · 완료 ✓ | `GET /notebook` |

### 3.3 표현 익히기 `learn.html`
| 요소 | 동작 | API |
|---|---|---|
| 단어 8 (가로 스크롤) | 탭하면 듣기 | `GET /words` · `GET /tts/{id}` |
| 패턴 카드 3 | 문장 · 뜻 · 규칙 힌트 · 듣기 · 다음 | `GET /patterns` · `GET /tts/{id}` |
| [이 표현으로 말해보기] | → 튜터 | — |

### 3.4 내 문장 말해보기 `tutor.html` (핵심)
| 요소 | 동작 | API |
|---|---|---|
| 미션 문구 · 힌트 단어 | Unit 데이터에서 | `GET /units` |
| 🎙 말하기 | 녹음 최대 6초 → STT → "들린 문장" | `POST /speak` (heard 만 사용) |
| ⌨ 쓰기 | 입력창 | — |
| [고쳐줘] | 3단계 표시(받기 → RAG 검색 → AI 설명) 후 진단 | `POST /fix` |
| 진단 카드 | 규칙명 · ~~틀린 말~~ 고친 말 · 고친 문장 · 설명 · 근거(조각 id · 점수 · 2위) · 🔊 고친 문장 듣기 | `GET /tts/{id}` (고친 문장은 `POST /tts/text`, 미정) |
| 🙋 물어보기 | 시트 열기 (3.8) | — |
| [다른 문장] / [오답노트] | 초기화 / 이동 | — |

상태 표시: 30초 넘으면 "규칙 전부 참고 모드로 전환" (RAG 실패 폴백).

### 3.8 물어보기 챗 시트 (Unit 안 5화면 공통 · TTS 팀원)
| 요소 | 동작 | API |
|---|---|---|
| 🙋 버튼 | 표현 익히기 · 따라 말하기 · 튜터 · 오답노트 · 연습 화면 오른쪽 아래. 시작 · Unit 목록엔 없음 | — |
| 문맥 칩 | Unit · (튜터) 직전 진단 규칙 · (오답노트) 헷갈리는 규칙 수 | 화면 상태 |
| 추천 질문 3 | 화면·문맥에 따라 다름. 서버가 줌 | `POST /ask` 응답의 `suggested` 또는 `GET /ask/suggest?screen=&context=` |
| 입력 · 🎙 | 직접 입력, 음성은 STT(heard)만 사용 | `POST /speak` |
| 답 | 2~3문장 + 📚 근거 id. 조각 밖 질문은 "그건 영어 공부랑 조금 다른 것 같아" | `POST /ask` |
| 턴 제한 | 3턴 후 "돌아갈게요" 버튼 (미정) | — |

### 3.5 오답노트 `notebook.html`
| 요소 | 동작 | API |
|---|---|---|
| 규칙 카드 | 규칙명 · 횟수 · 최근 · 내 문장 → 고친 문장 · 근거 id | `GET /notebook?student=` |
| [이 규칙 연습하기] | → 규칙 연습 | — |
| 극복한 규칙 | 연속 2회 정답 | 같은 응답 |

### 3.6 규칙 연습 `drill.html`
| 요소 | 동작 | API |
|---|---|---|
| 문장 (밑줄) + 보기 4 | 고칠 말 고르기 · 즉시 채점 · 답 뒤 규칙 조각 | `GET /drill?student=&rule=` · `POST /drill/answer` |
| 2문제 다 맞히면 | streak +1 (2면 극복) | 서버가 처리 |

### 3.7 관리자 `admin.html`
| 요소 | 동작 | API |
|---|---|---|
| 골든 데이터 표 | 파일별 개수 | `GET /health` |
| 정확도 카드 · 그래프 | hit@3 · hit@1 · 조립 방식별 runs | `GET /rag/eval` |
| 학생 문장 로그 | 규칙별 걸린 횟수 · 예시 | `GET /admin/log` |

## 4. API 명세

베이스 `/api`. JSON. 오류 `{"detail": "..."}`. **계약 변경은 셋 합의.**

### 4.1 골든 데이터 — TTS 담당 · `golden.py`
```
GET /levels                    → [{"level":2,"label":"Level 2 · 5학년","units":3}]
GET /units?level=2             → [{"unit":"U3","title":"Animals","mission":"어제 동물원에서 본 것을 말해봐요","hint_words":["rabbit","lion","saw","yesterday"],"rules":["R-01","R-03"]}]
GET /words?level=2&unit=U3     → [{"id":"w-0031","word":"rabbit","meaning":"토끼","example":"I saw a rabbit."}]
GET /patterns?level=2&unit=U3  → [{"id":"p-0001","text":"I saw a rabbit.","meaning":"나는 토끼를 봤어요.","tip":"과거를 말할 땐 동사를 과거형으로","rule_id":"R-01"}]
```

### 4.2 RAG — RAG 담당 · `rag.py`
```
GET /rag/search?q=I go to the zoo yesterday&kind=rule&k=3
→ {"query":"...","hits":[{"id":"R-01","kind":"rule","name":"과거시제","text":"yesterday, last week처럼 …","score":0.91},
                          {"id":"R-03","kind":"rule","name":"관사","text":"…","score":0.42}, ...],
   "threshold":0.60}
   kind: rule (규칙 조각) | explain (설명·FAQ 조각) | all
   역할: 질문/문장의 표현이 어떻든 올바른 조각에 도착시키는 것(깔때기). hit@3 = 이 도착률. 규모가 작아 키워드 검색과 병행(하이브리드)도 실험 항목
   score < threshold 이면 호출자가 "해당 없음"으로 판단. threshold 는 rag.py 상수 (평가셋으로 조정)

GET /rag/eval
→ {"n":30,"hit_at_3":0.87,"hit_at_1":0.70,"threshold":0.60,
   "runs":[{"label":"규칙만","hit_at_3":0.63},{"label":"규칙+예시","hit_at_3":0.77},{"label":"규칙+예시+한국어","hit_at_3":0.87}]}
```

### 4.3 튜터 — 팀장 · `tutor.py`
```
POST /fix
{"student":"A","level":2,"unit":"U3","text":"I go to the zoo yesterday","source":"stt"|"typed"}
→ {"ok":false,
   "rule":{"id":"R-01","name":"과거시제","score":0.91},
   "runner_up":{"id":"R-03","name":"관사","score":0.42},
   "wrong":"go","fix":"went","fixed":"I went to the zoo yesterday.",
   "why":"yesterday처럼 지난 일을 말할 때는 동사를 과거형으로 써요. go는 went가 돼요.",
   "source":{"chunk_id":"R-01","text":"yesterday, last week처럼 …"},
   "more_errors":false,
   "suggested_questions":["왜 went예요?","yesterday 대신 뭘 쓸 수 있어요?","다른 예문 보여줘"],
   "log_id":"L-20260910-0007"}
   ok=true 이면 rule=null, wrong/fix=null, why="문법에 맞는 문장이에요…"
   처리: rag.search(text, kind=rule) → 1위 score ≥ threshold 면 그 조각만 프롬프트에 넣어 Gemini(JSON 강제) → 오답노트 기록 + 문장 로그
   폴백: 검색 실패/타임아웃 → 규칙 조각 전부(≤30)를 프롬프트에 넣어 생성, 응답에 "mode":"fallback"

POST /ask                                    담당: TTS 팀원 (chat.py)
{"student":"A","question":"왜 went예요?",
 "context":{"screen":"tutor","unit":"U3","log_id":"L-...","rule_id":"R-01"}}
→ {"answer":"go의 과거형은 규칙 없이 went로 바뀌어요…","source":[{"chunk_id":"R-01"},{"chunk_id":"R-05"}],
   "suggested":["yesterday 대신 뭘 쓸 수 있어요?","다른 예문 보여줘"],"offtopic":false}
   처리: rag.search(question, kind=all(rules·faq·patterns), k=3) → 1위 < threshold 면 offtopic=true(정중 거절) → 조각 + context(직전 진단·오답노트 요약) 를 prompts/ask.txt 에 → Gemini
   대화 이력은 세션 내 최근 3턴만 프롬프트에 포함
```

### 4.4 오답노트 · 연습 — `student.py`(TTS 팀원) · `drill.py`(팀장)
```
GET /notebook?student=A
→ {"active":[{"rule_id":"R-01","name":"과거시제","count":3,"last":"2026-09-10","streak":0,
              "examples":[{"text":"I go to the zoo yesterday.","fixed":"I went to the zoo yesterday.","log_id":"L-..."}]}],
   "overcome":[{"rule_id":"R-02","name":"3인칭 단수"}]}

GET /drill?student=A&rule=R-01&count=2
→ {"drill_id":"D-...","questions":[{"id":"d1","sentence":"I go to the zoo yesterday.","target":"go","choices":["went","goes","going","gone"],"answer":0,"error_id":"E-0012"}]}
   출처: errors.jsonl 중 rule_id 일치 · 보기는 target 동사 변형 (코드 규칙) 또는 errors 의 distractors

POST /drill/answer
{"student":"A","drill_id":"D-...","question_id":"d1","choice":0}
→ {"correct":true,"answer":0,"rule_text":"yesterday, last week처럼 …"}
   drill 2문제 모두 정답 → notebook streak+1 (2면 overcome), 하나라도 오답 → streak 0

GET /admin/log?days=7
→ {"rows":[{"rule_id":"R-01","name":"과거시제","count":14,"students":2,"example":"I go to the zoo yesterday."}]}
```

### 4.5 음성 — TTS 담당 (완성, 그대로)
```
GET  /tts/{item_id}        단어 · 패턴 id → wav
POST /speak                 {student,item_id?,audio_base64,mime} → {heard,...}   튜터는 heard 만 사용 (item_id 생략 허용으로 변경 필요)
```
**변경 요청**: `/speak` 의 `item_id` 를 선택으로 (없으면 채점 없이 heard 만 반환). `/tts/text` (임의 문장 → wav, 캐시 키 = 해시) 추가 — 고친 문장 듣기용.

### 4.6 공통
```
GET /health → {"ok":true,"api_key":true,"model":"...","golden":{"rules":25,"words":40,"patterns":20,"errors":40,"eval":30},"using_sample":false}
```

## 5. 데이터 명세

### 5.1 골든 (데이터팀 → `data/golden/`)

| 파일 | 한 줄 | 컬럼 |
|---|---|---|
| `rules.jsonl` ★ | 규칙 설명 조각 | id(R-01) · type(과거시제) · unit · text(검색용 본문: 상황 표현어 + 규칙 + 예시 + 한국어) · short(한 줄 힌트) · examples[] |
| `words.csv` | 단어 | id · level · unit · word · meaning · example |
| `patterns.csv` | 문장 패턴 | id · level · unit · text · meaning · tip · rule_id |
| `errors.jsonl` | 오류 예시 | id(E-0012) · unit · rule_id · error · correct · target · fix · distractors[] |
| `eval.csv` | 평가 | text(학생 문장) · expected_rule_id · note. **정상 문장 5개는 expected="NONE"** |
| `faq.jsonl` | 물어보기 챗 답변 조각 | id(F-01) · unit · question · answer · rule_ids[] · 검색 대상(kind=faq) |
| `units.csv` | Unit | level · unit · title · mission · hint_words · rule_ids |

조각 텍스트 예 (R-01):
```
{"id":"R-01","type":"과거시제","unit":"U3",
 "text":"어제(yesterday), 지난주(last week)처럼 지난 일을 말할 때는 동사를 과거형으로 써요. go는 went, see는 saw, eat는 ate가 돼요. 예: I went to the zoo yesterday. I saw a lion. 틀린 예: I go to the zoo yesterday.",
 "short":"과거를 말할 땐 동사를 과거형으로","examples":["I went to the zoo yesterday.","I saw a lion."]}
```
→ 검색이 잘 되려면 **학생이 쓸 법한 말(yesterday, go, zoo)과 틀린 예까지** 본문에 넣는다. 세부: data-pipeline-plan-B 4절.

### 5.2 학생 DB (`data/student/` · `student.py`)
```
notebook.json       {"A":{"R-01":{"count":3,"last":"2026-09-10","streak":0,"log_ids":["L-..",...]}}}
sentence_log.jsonl  {"log_id":"L-..","ts":"...","student":"A","unit":"U3","text":"I go ...","source":"stt","rule_id":"R-01","score":0.91,"ok":false,"fixed":"...","mode":"rag"}
drill_log.jsonl     {"ts":"...","student":"A","rule_id":"R-01","correct":true}
```

### 5.3 RAG 저장소 (`data/chroma/` · RAG 담당)
컬렉션 `rules` (rules.jsonl 임베딩, 메타: type · unit) · `explain` (rules + patterns 의 설명, 더 물어보기용). chunks 가 바뀔 때만 재생성. 조립 실험은 `text` 구성 3종.

## 6. 프롬프트 (`backend/prompts/`)

| 파일 | 변수 | 규칙 |
|---|---|---|
| `fix.txt` | {{sentence}} {{rule_text}} {{unit_words}} | "참고 규칙만 근거로", 틀린 부분 하나, 초등 3학년 2문장, 규칙에 없으면 만들지 않기, JSON 스키마 |
| `fix_fallback.txt` | {{sentence}} {{all_rules}} | 검색 실패 시. 규칙 목록 중 하나를 고르게 |
| `ask.txt` | {{question}} {{chunks}} {{last_diagnosis}} | 조각 근거 답 2~3문장, 출처 id 나열 |

## 7. 점수 · 판정 규칙

| 항목 | 기본값 | 조정 |
|---|---|---|
| threshold (걸리는 규칙 없음) | 0.60 | RAG 담당이 평가셋 정상 문장 5개로 조정 |
| 오류 2개 이상 | 1위만 고치고 `more_errors:true` → 화면 "하나 더 있어요, 다시 고쳐줘" | 미정 |
| 극복 | 연습 2문제 연속 2회 전부 정답 | |
| 우선 출제 | 오답노트 count 내림차순 | |

## 8. 비기능

| 항목 | 기준 |
|---|---|
| `/fix` 응답 | ≤ 15초 목표 (검색 <1초 + Gemini). 30초 초과 → 폴백 |
| 키 · 비용 | `.env` · 무료 티어 · 임베딩 1회 · TTS 캐시 |
| 마이크 | localhost 보장 · 거부 시 ⌨ 로 안내 |

## 9. 성공 지표

| 지표 | 목표 | 측정 |
|---|---|---|
| 문장 → 규칙 hit@3 | ≥ 80% | eval.csv 30 · `/rag/eval` |
| 정상 문장 오탐 | ≤ 1/5 | eval 의 NONE 5개 |
| `/fix` JSON 성공률 | ≥ 95% | sentence_log |
| 데모 | 시나리오 8단계 통과 | 리허설 |

## 10. 마일스톤

| 일차 | 완료 기준 |
|---|---|
| 2 | 임시 rules 6개 · `/rag/search` 스텁이라도 `/fix` 폴백 모드로 진단 동작 · 튜터 화면 표시 |
| 5 | Chroma 검색 동작 · `/fix` rag 모드 · 오답노트 저장 |
| 8 | 골든 데이터 교체 · `/ask` · 규칙 연습 · hit@3 1차 |
| 11 | 조립 실험 3종 · 관리자 그래프 · 문장 로그 |
| 13 | **기능 동결** |
| 15 | 발표 |

## 11. 미정 (기본값으로 착수)

| 항목 | 기본값 |
|---|---|
| 오류 유형 6개 | 과거시제 · 3인칭단수 · 명사복수 · be동사 · 관사 · 현재진행 |
| 오류 2개 처리 | 1위만 + more_errors |
| 고친 문장 듣기 | `/tts/text` 추가 (TTS 담당 합의) |
| 단어 4지선다 | △ 시간 남으면 |
| 챗 턴 제한 · 추천 질문 출처 | 3턴 · faq.jsonl 에서 |
| BigQuery 주간 리포트 | 11일차 여유 시. sentence_log → 집계 → Gemini 리포트 문장 (관리자 패널) |
| 표현 익히기 범위 | 단어 8 + 패턴 3 (축소) |
