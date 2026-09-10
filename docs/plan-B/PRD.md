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
| RAG 입구 | ① 문장 → 규칙 (`/fix`) ② 질문 → 설명 조각 (`/ask`, **RAG 연결 예정** — 지금은 FAQ 매칭 + LLM) |
| DB 조회 (RAG 아님) | 오답노트 · 패턴 · 단어 · 규칙 연습 문제 |
| RAG의 역할 | **깔때기**(다양한 질문·라벨 없는 문장 → 올바른 조각) + **목줄**(조각 밖 내용 생성 금지). 지식 확장이 아님 → [docs/README 공통 전제](../README.md) |
| 발표 핵심 | "🎙 → 검색 점수 → went + 근거" / "문장→규칙 hit@3 89% (65문항, hit@1 77%)" / "DB와 RAG를 구분해 썼다" |

## 2. 사용자 시나리오 (데모 60초)

1. 학생 A → Level 3 → Unit (Unit01~Unit20 중 하나, 예: "어제 한 일") (배지: 헷갈리는 규칙 2)
2. 표현 익히기: 패턴 "I saw a rabbit." 듣기
3. 내 문장: 🎙 "I go to the zoo yesterday" → 들린 문장 표시
4. 고쳐줘 → ① 받기 ② RAG 검색 ③ AI 설명 순서로 표시
5. 결과: 헷갈린 규칙 과거시제 · ~~go~~ went · 설명 2문장 · 근거 R-31 (점수 0.45, 2위 관사 R-34 0.38)
6. 더 물어보기 칩 "왜 went예요?" 탭 → 🙋 물어보기 시트가 열림 (맥락 칩: Unit · 방금: 과거시제)
   - 답 2~3문장 + 근거 R-31 · F-01 표시
   - 이어서 직접 입력 "yesterday 대신 뭘 쓸 수 있어요?" → 근거 붙은 답 (last week, ago)
   - 범위 밖 질문 "오늘 저녁 뭐 먹지?" → 검색 점수 낮음 → 정중 거절 ("영어 공부랑은 조금 다른 것 같아, 선생님께 물어볼까?")
   - 3턴 뒤 [이제 돌아갈게요 ↩] 로 시트 닫기 (질문은 글자로만, 🎙 없음 — STT 가 영어 전용)
7. 오답노트: 과거시제 3회 · 내 문장/고친 문장 · [연습하기] → 2문제 (여기서도 🙋 로 "이 규칙 예문 더 보여줘" 가능)
8. 학생 B로 바꾸면 오답노트 비어 있음 · 관리자: 정확도 그래프

## 3. 화면 명세 (팀장)

공통: 화면별 HTML + JS, 상태는 `common.js` 의 `S.get/S.set`. 모바일 375px 우선.

### 3.1 시작 `index.html`
| 요소 | 동작 | API |
|---|---|---|
| 학생 드롭다운 | A / B | — |
| Level 카드 | Level 3만 활성 (Unit01~Unit20) | `GET /levels` |
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
| 진단 카드 | 규칙명 · ~~틀린 말~~ 고친 말 · 고친 문장 · 설명 · 📚 근거 · 철자만 틀린 경우 "철자만 살짝" 한 줄 · 규칙 밖(OTHER) 카드. 🔊 고친 문장 듣기는 **미구현·보류** (`/tts/text` 없음) | — |
| 📚 근거 박스 (두 겹) | **학생용(기본)**: 규칙 `short` 한 줄만. **발표·개발용(토글)**: + 조각 id · 검색 점수(순위) · 2위 · 근거 원문 · 후보 5 · 모델(backend·model) · 응답시간(timing) · 모드 배지. 토글은 상단 학생 칩 **길게 누르기 또는 더블클릭** (구현 완료) | — |
| [다시 고쳐줘] | `more_errors` 면 카드 아래 버튼 → 고친 문장으로 `/fix` 재호출, 이전 카드 "n차 고침"으로 유지. 최대 2회. 2회 뒤에도 남으면 `full_fixed` 를 "다 고치면 이렇게 돼요" 로 표시 | `POST /fix` |
| 🙋 물어보기 | 시트 열기 (3.8) | — |
| [다른 문장] / [오답노트] | 초기화 / 이동 | — |

상태 표시: 로딩바(`setBusy`) + 경과 초 표시. 검색 실패(`search_error` · `no_results`) 시에만 규칙 전부를 프롬프트에 넣는 폴백(`mode:"fallback"`)으로 넘어간다. 시간 초과는 LLM 쪽(`LLM_TIMEOUT`)에서 다른 백엔드로 대체하거나 502.

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
| 골든 데이터 표 | 파일별 개수 · 색인 여부 · 색인 정보(개수 · 임베딩 모델 · 생성 시각) · 색인 stale 경고 | `GET /admin/golden` |
| RAG 정확도 카드 · 그래프 | hit@3 · hit@1 · 채점 문장 수 · runs(임베딩 모델별) 막대 | `GET /rag/eval` |
| STT 정확도 | 자리만 (TTS 담당 실험 결과 붙일 곳, API 미정) | — |
| 학생 문장 로그 | 규칙별 걸린 횟수 · 학생 수 · 예시 · 모델별 처리 수 | `GET /admin/log?days=` |
| 못 짚은 문장 표 | "우리 규칙으로 못 짚은 문장 · 데이터팀 안건" — 규칙 밖(OTHER) · 진단 실패 문장 | 같은 응답의 `gaps` |

## 4. API 명세

베이스 `/api`. JSON. 오류 `{"detail": "..."}`. **계약 변경은 셋 합의.**

### 4.1 골든 데이터 — TTS 담당 · `golden.py`
```
GET /levels                    → [{"level":3,"label":"Level 3 · 6학년","units":20}]
GET /units?level=3             → [{"unit":"Unit01","title":"Greetings (인사)","mission":"친구를 만나거나 헤어질 때 하는 인사말을 영어로 말해봐요","hint_words":["hello","hi","bye","morning","night"],"rule_ids":["R-32","R-38","R-01","R-02"]}]
GET /words?level=3&unit=Unit01 → [{"id":"w-0001","word":"hello","meaning":"안녕","example":"Hello, my friend."}]
GET /patterns?level=3&unit=Unit01 → [{"id":"p-0001","text":"I am happy.","meaning":"나는 행복해요.","tip":"형용사 앞엔 be동사","rule_id":"R-01"}]
   (납품본: Level 3 하나 · Unit01~Unit20 · Unit당 단어 20 · 패턴 20. 위 값은 형식 예시)
```

### 4.2 RAG — RAG 담당 · `rag.py`
```
GET /rag/search?q=I go to the zoo yesterday&level=3&k=3
→ {"query":"...","chunks":[{"id":"R-31","type":"과거시제","text":"어제(yesterday), 지난주(last week)…","unit":"ALL","score":0.45},
                            {"id":"R-34","type":"관사","text":"…","unit":"ALL","score":0.38}, ...],
   "threshold":null,"score_type":"cosine_similarity"}
   파이썬에서는 rag.search_rules(text, k) → [{id,type,text,unit,score}]. kind 구분 없음(규칙 조각만 색인). 어휘 안전망(lexical safety net)은 2026-09-10 제거 — 순수 임베딩 순위만 쓰고 R-01 같은 약점은 규칙 데이터 보강으로 해결
   역할: 질문/문장의 표현이 어떻든 올바른 조각에 도착시키는 것(깔때기). hit@3 = 이 도착률
   threshold 는 쓰지 않는다(null). "해당 없음"은 점수가 아니라 /fix 의 모델 판정(ok=true)으로

GET /rag/eval        data/rag_eval/retrieval_eval_latest.json 을 그대로 돌려줌
→ {"n":65,"total_n":72,"normal_n":7,"hit_at_1":0.7692,"hit_at_3":0.9231,"threshold":null,"k":3,
   "index":{"active_collection":"rules_20260910_071602170875","model":"gemini-embedding-001","dim":3072},
   "runs":[{"label":"gemini-embedding-001","hit_at_1":0.7692,"hit_at_3":0.9231}], "rows":[...]}
   n = 채점 문장(오류 65). 정상 문장 7개는 검색 평가에서 채점하지 않음
```

### 4.3 튜터 — 팀장 · `tutor.py`
```
POST /fix
{"student":"A","level":3,"unit":"Unit01","text":"I go to the zoo yesterday","source":"stt"|"typed"}
→ {"ok":false,
   "rule":{"id":"R-31","name":"과거시제","score":0.45,"rank":1},
   "runner_up":{"id":"R-34","name":"관사","score":0.38,"rank":2},
   "wrong":"go","fix":"went","fixed":"I went to the zoo yesterday.",
   "why":"yesterday처럼 지난 일을 말할 때는 동사를 과거형으로 써요. go는 went가 돼요.",
   "source":{"chunk_id":"R-31","text":"어제(yesterday), 지난주(last week)…"},
   "more_errors":false,
   "full_fixed":"I went to the zoo yesterday.",
   "spelling":[],
   "suggested_questions":["왜 went예요?","yesterday 대신 뭘 쓸 수 있어요?","다른 예문 보여줘"],
   "mission":{"ok":true,"nudge":""},
   "log_id":"L-20260910-143012-123","mode":"rag","fallback_reason":null,
   "candidates":[{"id":"R-31","name":"과거시제","score":0.45},{"id":"R-34","name":"관사","score":0.38}, … 5개],
   "llm":{"backend":"local","model":"qwen2.5:32b-instruct","ms":4210,"fallback_from":null},
   "timing":{"search_ms":320,"llm_ms":4210,"llm_calls":1,"total_ms":4600}}
   mission: 문법과 별개로 미션(units.mission)에 맞는 말인지. ok=false 면 nudge 한 문장 (화면 🎯 줄)
   full_fixed: 목록 규칙 기준으로 전부 고친 문장. fixed 는 1위 규칙 하나만 고친 문장 (서버가 wrong→fix 한 곳만 적용해 강제)
   rule.rank / runner_up.rank: 검색 순위 (모델이 검색 1위가 아닌 규칙을 고를 수도 있음). candidates: 검색 상위 5 (관리자·발표용)
   spelling: 철자만 틀린 경우 [{"wrong","fix"}] (ok=true 여도 옴). suggested_questions: 서버가 faq.jsonl 에서 고름
   mode: "rag" | "fallback" · fallback_reason: search_error | no_results | null
   ok=true 이면 rule=null, wrong/fix=null, why="문법에 맞는 문장이에요…"
   rule.id="OTHER"(규칙 밖): 우리 규칙 어디에도 안 맞는 문제. wrong/fix=null, fixed·full_fixed 는 학생 단어만으로 고친 문장. 화면은 "규칙 밖" 카드
   처리: 철자 사전검사 → rag.search_rules(text, k=전체) 로 점수·순위 확보 → 프롬프트에 상위 5 + 이 Unit 의 rule_ids + 공통(unit=ALL) 규칙 + 가짜 규칙 SPELL·OTHER → LLM(JSON) → 서버 검증 → 오답노트 기록 + 문장 로그. threshold 없음 — 정오는 모델이 판정
   폴백: 검색 실패(search_error · no_results) → 규칙 38개 전부를 프롬프트에 넣어 생성, 응답에 "mode":"fallback"

   철자 · 규칙 밖 · 서버 검증 · 재확인 · timing (현재 /fix 동작 요약)
   - 철자: pyspellchecker 로 사전검사 (교재 단어 우선). 철자만 틀리면 spelling 으로 알려 주고 문법은 ok 로 둘 수 있음
   - 규칙 밖: 프롬프트에 SPELL(철자) · OTHER(규칙 밖) 가짜 규칙을 넣어 "우리 규칙에 없음"도 답이 되게 함 → 관리자 "못 짚은 문장" 표로 감
   - 서버 검증(_pair_problem): 학생 단어 보존, 기능어 추가·어형 변화는 허용, 시간 표현 변경·지어낸 단어·어순 바꾸기는 거절(어순 규칙만 재배열 허용) → 1회 재시도 → 그래도 안 되면 full_fixed 가 학생 단어만으로 되어 있을 때 OTHER 로 살림, 아니면 502 (로그에 failed)
   - 재확인(_second_opinion): is→are, a→an 같은 기능어 한 개 교체는 LLM 을 한 번 더 불러 확인. "고칠 것 없음" 답은 재시도 후 ok 처리
   - timing: {search_ms, llm_ms, llm_calls, total_ms} — 발표용 근거 박스와 sentence_log 에 기록

POST /ask                                    담당: TTS 팀원 (ask.py)
{"student":"A","question":"왜 went예요?",
 "context":{"screen":"tutor","unit":"Unit01","log_id":"L-...","rule_id":"R-31"}}
→ {"answer":"go의 과거형은 규칙 없이 went로 바뀌어요…","source":[{"chunk_id":"R-31"},{"chunk_id":"F-01"}],
   "suggested":["yesterday 대신 뭘 쓸 수 있어요?","다른 예문 보여줘"],"offtopic":false}
   처리(현재): faq.jsonl(question+variants) · rules.jsonl 단어 겹침 로컬 매칭 → 맞으면 LLM 없이 즉시 답 → 없으면 FAQ 전체를 프롬프트에 넣어 llm.py 로 생성. **rag.search 는 아직 호출하지 않음** (RAG 연결 예정)
   대화 이력은 세션 내 최근 3턴만 프롬프트에 포함
```

### 4.4 오답노트 · 연습 — `student.py` · `drill.py` (팀장)
```
GET /notebook?student=A
→ {"active":[{"rule_id":"R-01","name":"과거시제","count":3,"last":"2026-09-10","streak":0,
              "examples":[{"text":"I go to the zoo yesterday.","fixed":"I went to the zoo yesterday.","log_id":"L-..."}]}],
   "overcome":[{"rule_id":"R-02","name":"3인칭 단수"}]}

GET /drill?student=A&rule=R-31&count=2
→ {"drill_id":"D-...","rule_id":"R-31","rule_name":"과거시제",
   "questions":[{"id":"d1","sentence":"I go to the zoo yesterday.","target":"go","choices":["went","goes","going","gone"],"error_id":"E-0012"}]}
   출처: errors.jsonl 중 rule_id 일치 · 보기 = fix + distractors 3개 (섞음). 정답 번호는 응답에 없음 (서버가 들고 있음)

POST /drill/answer
{"student":"A","drill_id":"D-...","question_id":"d1","choice":0}
→ {"correct":true,"answer":0,"rule_text":"어제(yesterday), 지난주(last week)…","done":false,"all_correct":null,"streak":null,"overcome":false}
   done: 이 drill 의 문제를 다 풀었는지. 다 풀면 all_correct · streak(갱신 후) 가 채워짐. 2문제 모두 정답 → notebook streak+1 (2면 overcome=true), 하나라도 오답 → streak 0

GET /admin/log?days=7                        admin.py
→ {"days":7,"n":42,"ok_n":9,"students":2,"llm":{"local":40,"gemini":2},
   "rows":[{"rule_id":"R-31","name":"과거시제","count":14,"students":2,"example":"I go to the zoo yesterday."}],
   "gaps":[{"ts":"2026-09-10T14:30:12","text":"I like apple very","fixed":"I like apples very much.","kind":"규칙 밖","reason":""}]}
   gaps: rule_id=OTHER(규칙 밖) 또는 진단 실패(failed) 문장 — 관리자 "우리 규칙으로 못 짚은 문장 · 데이터팀 안건" 표

GET /admin/golden                            admin.py
→ {"dir":"data/golden","using_sample":false,
   "files":[{"file":"rules.jsonl","desc":"규칙 조각","indexed":true,"count":38}, …],
   "index":{"count":38,"model":"gemini-embedding-001","generated_at":"2026-09-10T07:16:02"},"index_stale":false}
   index_stale: rules 개수와 색인 개수가 다르면 true → `python -m backend.indexing --rebuild` 안내
```

### 4.5 음성 — TTS 담당 (완성, 그대로)
```
GET  /tts/{item_id}        단어 · 패턴 id → wav
POST /speak                 {student,item_id?,audio_base64,mime} → {heard,...}   튜터는 heard 만 사용 (item_id 생략 허용으로 변경 필요)
```
**변경 요청**: `/speak` 의 `item_id` 를 선택으로 (없으면 채점 없이 heard 만 반환). `/tts/text` (임의 문장 → wav, 캐시 키 = 해시) 추가 — 고친 문장 듣기용.

### 4.6 공통
```
GET /health → {"ok":true,"api_key":true,"model":"<.env GEMINI_MODEL>","golden_files":["rules.jsonl","faq.jsonl","errors.jsonl","eval.csv","units.csv","patterns.csv","words.csv"],"using_sample":false}
   파일별 개수·색인 상태는 GET /admin/golden
```

## 5. 데이터 명세

### 5.1 골든 (데이터팀 → `data/golden/`)

| 파일 | 한 줄 | 컬럼 |
|---|---|---|
| `rules.jsonl` ★ (38) | 규칙 설명 조각 | id(R-01~R-38) · type(과거시제) · unit(Unit01~Unit20 또는 ALL) · text(검색용 본문: 상황 표현어 + 규칙 + 예시 + 한국어) · short(한 줄 힌트) · examples[] · wrong_example |
| `words.csv` (400) | 단어 | id · level · unit · word · meaning · example |
| `patterns.csv` (400) | 문장 패턴 | id · level · unit · text · meaning · tip · rule_id |
| `errors.jsonl` (400) | 오류 예시 | id(E-0012) · unit · rule_id · error · correct · target · fix · distractors[] (3개 모두 채움) |
| `eval.csv` (72) | 평가 | text(학생 문장) · expected_rule_id · note. **정상 문장 7개는 expected="NONE"** (오류 65 + 정상 7) |
| `faq.jsonl` (74) | 물어보기 챗 답변 조각 | id(F-01) · unit · question · variants[] · answer · rule_ids[] · example. 색인은 아직 안 함(/ask 가 로컬 매칭) |
| `units.csv` (20) | Unit | level(전부 3) · unit(Unit01~Unit20) · title · mission · hint_words · rule_ids |

조각 텍스트 예 (R-31 · 과거시제 · 공통 규칙이라 unit=ALL):
```
{"id":"R-31","type":"과거시제","unit":"ALL",
 "text":"어제(yesterday), 지난주(last week), 아까(ago)처럼 지난 일을 말할 때는 동사를 과거형으로 써요. go는 went, see는 saw, eat는 ate가 돼요. 예: I went to the zoo yesterday. I saw a lion. 틀린 예: I go to the zoo yesterday.",
 "short":"과거를 말할 땐 동사를 과거형으로","examples":["I went to the zoo yesterday.","I saw a lion."],"wrong_example":"I go to the zoo yesterday."}
```
(R-01 은 납품본에서 "형용사+be동사 · Unit01". 규칙 38 = Unit별 30 + 공통(ALL) 8)
→ 검색이 잘 되려면 **학생이 쓸 법한 말(yesterday, go, zoo)과 틀린 예까지** 본문에 넣는다. 세부: data-pipeline-plan-B 4절.

### 5.2 학생 DB (`data/student/` · `student.py`)
```
notebook.json       {"A":{"R-01":{"count":3,"last":"2026-09-10","streak":0,"log_ids":["L-..",...]}}}
sentence_log.jsonl  {"log_id":"L-..","ts":"...","student":"A","level":3,"unit":"Unit01","text":"I go ...","source":"stt","spelled":null,"rule_id":"R-31","ok":false,"fixed":"...","mission_ok":true,"mode":"rag","fallback_reason":null,"top_score":0.45,"llm":"local","llm_ms":4210,"total_ms":4600,"search_ms":320,"llm_calls":1}
                    진단 실패 행은 rule_id/ok/fixed 가 null 이고 "failed":"이유" 가 붙음 (관리자 gaps 표 재료)
drill_log.jsonl     {"ts":"...","student":"A","rule_id":"R-01","correct":true}
```

### 5.3 RAG 저장소 (`data/chroma/` · RAG 담당)
컬렉션 `rules_<stamp>` (rules.jsonl 의 `text` 원문 임베딩, 메타: type · unit). 어느 컬렉션이 현재 것인지는 `data/chroma/manifest.json` 의 `active_collection` (+ 임베딩 모델 · dim · 규칙 수 · data_hash · 생성 시각). 임베딩은 `backend/embedding.py` 의 gemini-embedding-001 (3072차원). 재생성 `python -m backend.indexing --rebuild` (검증만은 `--validate-only`). `explain` 컬렉션은 없고 faq 색인은 미구현. 조립 실험은 text 구성이 아니라 임베딩 모델 비교로 진행했고 Gemini 채택.

## 6. 프롬프트 (`backend/prompts/`)

| 파일 | 변수 | 규칙 |
|---|---|---|
| `fix_fallback.txt` (유일한 프롬프트 파일) | {{mission}} {{hint_words}} {{all_rules}} {{sentence}} | rag · fallback 모드 공통. all_rules 에 검색 상위 5 + Unit 규칙 + 공통 규칙 + SPELL · OTHER (폴백이면 38개 전부). "참고 규칙만 근거로", 틀린 부분 하나, 초등 눈높이 2문장, 규칙에 없으면 OTHER, JSON 스키마 |

`/ask` 는 프롬프트 파일 없이 ask.py 안에서 FAQ 전체를 넣어 만든다 (별도 ask.txt 없음).

## 7. 점수 · 판정 규칙

| 항목 | 기본값 | 조정 |
|---|---|---|
| threshold (걸리는 규칙 없음) | **미설정 (null)** | 점수 기준으로 자르지 않고 모델이 ok=true 로 판정. 정상 문장 오탐은 eval 의 NONE 7개를 `/fix` 로 돌려 확인 (tests/eval_fix.py) |
| 오류 2개 이상 | 1위만 고치고 `more_errors:true` → 화면에 [고친 문장으로 다시 고쳐줘] 버튼 → 고친 문장으로 `/fix` 재호출, 이전 카드는 "1차 고침"으로 남김. **최대 2회**, 그 뒤에도 남으면 `full_fixed`(다 고친 문장)를 최종 정답으로 표시. 서버는 `fixed` 가 wrong→fix 한 곳만 바뀐 문장이 되도록 강제 | 확정 (2026-09-08) |
| 극복 | 연습 2문제 연속 2회 전부 정답 | |
| 우선 출제 | 오답노트 count 내림차순 | |

## 8. 비기능

| 항목 | 기준 |
|---|---|
| `/fix` 응답 | ≤ 15초 목표 (검색 <1초 + LLM). `LLM_TIMEOUT`(기본 30초) 초과 → `LLM_FALLBACK=1` 이면 다른 백엔드(gemini)로 대체, 아니면 502 |
| 키 · 비용 | `.env` · 무료 티어 · TTS 캐시. `/fix` 한 번에 Gemini 임베딩 호출 1회 (무료 티어 "Free of charge", 429 면 검색 실패 → 규칙 전부 폴백). 생성 LLM 은 `LLM_BACKEND` 로 교체 가능 (지금 강의실 서버 로컬 Qwen, 실패 시 Gemini flash-lite 무료 티어) |
| 마이크 | localhost 보장 · 거부 시 ⌨ 로 안내 |

## 9. 성공 지표

| 지표 | 목표 | 측정 |
|---|---|---|
| 문장 → 규칙 hit@3 | ≥ 80% (실제 89.23%, hit@1 76.92% — 검색 안전망 제거 후 09-10 재측정) | eval.csv 72 (채점 65) · `/rag/eval` |
| 정상 문장 오탐 | ≤ 1/7 | eval 의 NONE 7개. 검색 평가는 정상 문장 오탐을 판정하지 않음 → `/fix` 기준 (tests/eval_fix.py) |
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
| 오류 유형 | 규칙 38개로 납품 완료 (Unit별 30 + 공통 8: 과거시제 R-31 · 관사 R-34/R-38 등) |
| 오류 2개 처리 | 1위만 + more_errors → [다시 고쳐줘] 버튼, 최대 2회 (확정 2026-09-08) |
| 고친 문장 듣기 | 미구현 · 보류 (`/tts/text` 없음) |
| 단어 4지선다 | △ 시간 남으면 |
| 챗 턴 제한 · 추천 질문 출처 | 3턴 · faq.jsonl 에서 |
| BigQuery 주간 리포트 | 11일차 여유 시. sentence_log → 집계 → Gemini 리포트 문장 (관리자 패널) |
| 표현 익히기 범위 | 단어 8 + 패턴 3 (축소) |
