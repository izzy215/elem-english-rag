# 다이어그램 B — 유스케이스 · 시퀀스 (Mermaid)

작성 2026-09-06 · 근거: [PRD-B](PRD.md) · [mockup.html](mockup.html)
GitHub · VS Code(Mermaid 확장) · Notion 에서 그대로 렌더링됨.

---

## 1. 유스케이스 다이어그램

Mermaid에는 유스케이스 전용 문법이 없어 flowchart 로 표기 (타원 = 유스케이스, 사각 = 액터).

```mermaid
flowchart LR
  subgraph actors[" "]
    direction TB
    S([👦 학생])
    M([🧑‍💼 관리자])
    D([📚 데이터팀])
  end

  subgraph app["내 문장 고쳐주기 튜터"]
    direction TB
    UC1(["Level · Unit(미션) 고르기"])
    UC2(["표현 익히기<br/>단어 · 패턴 · 듣기"])
    UC3(["내 문장 말하기 / 쓰기"])
    UC4(["고쳐주기 받기<br/>규칙 · 고친 문장 · 근거"])
    UC5(["더 물어보기"])
    UC6(["오답노트 보기"])
    UC7(["규칙 연습하기<br/>4지선다"])
    UC8(["정확도 · 문장 로그 보기"])
    UC9(["골든 데이터 납품"])
  end

  subgraph ext["외부 · 내부 시스템"]
    direction TB
    STT[["로컬 Whisper STT<br/>(whisper_server.py)"]]
    TTS[["Gemini TTS"]]
    RAG[["RAG 검색<br/>Chroma · gemini-embedding-001"]]
    LLM[["LLM 생성<br/>(llm.py 스위치: 로컬 Qwen → Gemini)"]]
    DB[["학생 DB<br/>JSON"]]
  end

  S --> UC1 --> UC2 --> UC3 --> UC4 --> UC5
  UC4 --> UC6 --> UC7
  S --> UC6
  M --> UC8
  D --> UC9

  UC2 -. 듣기 .-> TTS
  UC3 -. 🎙 .-> STT
  UC4 -. "① 규칙 검색" .-> RAG
  UC4 -. "② 근거로 생성" .-> LLM
  UC4 -. 기록 .-> DB
  UC5 -. 설명 조각 검색 .-> RAG
  UC5 -. 생성 .-> LLM
  UC6 -. 읽기 .-> DB
  UC7 -. streak 갱신 .-> DB
  UC8 -. 집계 .-> DB
  UC9 -. 임베딩 .-> RAG

  %% 밝은 배경을 칠한 노드는 글자색을 직접 지정해야 다크 모드에서도 보임
  classDef core fill:#E4EFEA,stroke:#14554A,stroke-width:2px,color:#1F2823
  classDef rag fill:#FBF0DC,stroke:#E8A33D,stroke-width:2px,color:#1F2823
  class UC3,UC4 core
  class RAG rag
```

**포함 관계 요약**

| 유스케이스 | 액터 | 포함(include) | 확장(extend) |
|---|---|---|---|
| 고쳐주기 받기 | 학생 | 규칙 검색(RAG) · 근거로 생성(LLM) · 오답노트 기록 | 오류 없음 → "잘 썼어요" / 검색 실패 → 폴백(규칙 전부 참고) |
| 더 물어보기 | 학생 | FAQ 매칭 · 생성 (설명 조각 RAG 검색은 연결 예정) | 추천 질문 버튼 / 직접 입력 |
| 규칙 연습 | 학생 | 문제 꺼내기(DB) · 채점 · streak | 2회 연속 정답 → 극복 |
| 골든 데이터 납품 | 데이터팀 | 형식 검증 · 임베딩 · 임베딩 모델 비교 | |

---

## 2. 시퀀스 다이어그램 ① 고쳐주기 (핵심 · `/fix`)

```mermaid
sequenceDiagram
  autonumber
  actor S as 학생
  participant UI as tutor.html
  participant SP as speak.py<br/>(STT)
  participant WH as whisper_server.py<br/>(로컬 Whisper)
  participant TU as tutor.py<br/>(/fix)
  participant RG as rag.py<br/>(Chroma)
  participant LM as llm.py<br/>(LLM 스위치)
  participant ST as student.py<br/>(학생 DB)

  S->>UI: 🎙 말하기 (최대 6초)
  UI->>SP: POST /speak {audio_base64}
  SP->>WH: 오디오 → 받아쓰기 (강의실 GPU 서버, 없으면 로컬 CPU)
  WH-->>SP: "I go to the zoo yesterday"
  SP-->>UI: {heard}
  UI-->>S: 들린 문장 표시 · [고쳐줘]

  S->>UI: 고쳐줘
  UI->>TU: POST /fix {student, level, unit, text, source:"stt"}
  Note over UI: 화면: ① 문장 받기 ✓ (로딩바 + 경과 초)
  Note over TU: 철자 사전검사 (pyspellchecker, 교재 단어 우선)

  TU->>RG: search_rules(text, k=전체)
  Note over RG: 문장 임베딩(gemini-embedding-001) → 규칙 조각과 코사인 비교<br/>kind · threshold 없음 · R-01 은 어휘 안전망 보강
  RG-->>TU: [{R-31 과거시제 0.45}, {R-34 관사 0.38}, ...] 38개 전부 (점수 · 순위)
  Note over UI: 화면: ② RAG 규칙 검색 ✓

  alt 검색 성공 (mode: rag)
    TU->>LM: prompts/fix_fallback.txt {mission, hint_words, all_rules, sentence} · JSON<br/>all_rules = 검색 상위 5 + 이 Unit 규칙 + 공통(ALL) 규칙 + SPELL · OTHER
  else 검색 실패 (mode: fallback, fallback_reason: search_error 또는 no_results)
    TU->>LM: 같은 프롬프트, all_rules = 규칙 38개 전부 + SPELL · OTHER
  end
  LM-->>TU: {ok:false, rule_id:"R-31", wrong:"go", fix:"went", fixed:"I went…", full_fixed, why, more_errors, mission}
  Note over TU: 서버 검증(_pair_problem) → 안 맞으면 1회 재시도 → OTHER 로 살림 또는 502<br/>기능어 한 개 교체(is→are, a→an)는 _second_opinion 으로 한 번 더 확인
  alt ok=false (규칙에 걸림 · OTHER 포함)
    TU->>ST: 오답노트 기록 (R-31 count+1, streak 0) + 문장 로그
  else ok=true (잘 썼어요 · 철자만 틀림)
    TU->>ST: 문장 로그만
  end
  Note over UI: 화면: ③ AI 설명 ✓

  TU-->>UI: {ok, rule{id,name,score,rank}, runner_up, wrong, fix, fixed, why, source, more_errors, full_fixed,<br/>spelling, suggested_questions, mission, log_id, mode, fallback_reason, candidates(5), llm, timing}
  UI-->>S: 진단 카드 · 근거(R-31 · 0.45 · 발표용 토글이면 후보 5 · 모델 · timing) · 더 물어보기 칩 최대 3개(FAQ) + 직접 물어보기
```

---

## 3. 시퀀스 다이어그램 ② 더 물어보기 (`/ask`)

```mermaid
sequenceDiagram
  autonumber
  actor S as 학생
  participant UI as tutor.html
  participant AK as ask.py<br/>(/ask)
  participant FQ as faq.jsonl · rules.jsonl<br/>(로컬 매칭)
  participant LG as sentence_log.jsonl
  participant LM as llm.py<br/>(LLM 스위치)

  S->>UI: "왜 went예요?" (추천 버튼 또는 직접 입력)
  UI->>AK: POST /ask {student, question, context{screen, unit, rule_id, log_id}}
  AK->>FQ: question + variants 단어 겹침 매칭 (1순위 faq, 2순위 rules)
  alt 매칭됨 (점수 0.5 이상)
    FQ-->>AK: F-01 답 + rule_ids
    Note over AK: LLM 호출 없이 즉시 반환
  else 매칭 안 됨
    AK->>LG: log_id 로 직전 진단 읽기 (원문 · 고친 문장)
    LG-->>AK: last_diagnosis
    AK->>LM: FAQ 전체 + 질문 + last_diagnosis 를 프롬프트에 · JSON
    LM-->>AK: "go의 과거형은 규칙 없이 went로…" + 근거 id · offtopic
  end
  AK-->>UI: {answer, source:[R-31, F-01], suggested, offtopic, llm}
  UI-->>S: 답 + 📚 근거 id
  Note over AK: rag.search 는 아직 호출하지 않음 (RAG 연결 예정)
```

---

## 4. 시퀀스 다이어그램 ③ 오답노트 → 규칙 연습 → 극복

```mermaid
sequenceDiagram
  autonumber
  actor S as 학생
  participant NB as notebook.html
  participant DR as drill.html
  participant ST as student.py<br/>(/notebook)
  participant DL as drill.py<br/>(/drill)
  participant GD as golden.py<br/>(errors.jsonl)

  S->>NB: 📒 오답노트
  NB->>ST: GET /notebook?student=A
  ST-->>NB: {active:[R-01 과거시제 count 3 streak 0 …], overcome:[R-02]}
  NB-->>S: 규칙 카드 · 내 문장 → 고친 문장 · [이 규칙 연습하기]

  S->>DR: 과거시제 연습하기
  DR->>DL: GET /drill?student=A&rule=R-01&count=2
  DL->>GD: rule_id=R-01 인 오류 예시 2개
  GD-->>DL: [{E-0012 "I go to the zoo yesterday." target go}, …]
  Note over DL: 보기 = fix + distractors (코드 규칙, AI 없음)
  DL-->>DR: {drill_id, questions[2]}

  loop 문제 2개
    S->>DR: 보기 선택
    DR->>DL: POST /drill/answer {drill_id, question_id, choice}
    DL-->>DR: {correct, answer, rule_text}
    DR-->>S: 정답/오답 · 규칙 조각 해설
  end

  DL->>ST: 2문제 모두 정답 → streak+1 / 아니면 streak 0
  alt streak == 2
    ST-->>NB: R-01 → overcome 으로 이동
    NB-->>S: "극복한 규칙 ○ 과거시제"
  else
    NB-->>S: 여전히 active (한 번 더!)
  end
```

---

## 5. 시퀀스 다이어그램 ④ 골든 데이터 납품 → 인덱스 → 평가 (개발팀 내부)

```mermaid
sequenceDiagram
  autonumber
  actor D as 데이터팀
  participant G as data/golden/
  participant I as backend/indexing.py<br/>(RAG 담당)
  participant EM as backend/embedding.py<br/>(gemini-embedding-001)
  participant C as Chroma<br/>(data/chroma/)
  participant E as tests/eval_rag.py
  participant A as admin.html

  D->>G: rules · faq · errors · eval · units · patterns · words 납품
  I->>G: --validate-only 형식 검증 (컬럼 · id 중복 · rule_id 참조)
  I-->>D: 오류 목록 (있으면 수정 요청)
  I->>G: --rebuild rules.jsonl 읽기
  I->>EM: text 원문 임베딩 (조각당 1회, 3072차원)
  I->>C: 컬렉션 rules_20260910_… 생성 → manifest.json 의 active_collection 갱신
  E->>C: eval.csv 72문장 중 오류 65문장 각각 search(k=3) (정상 7은 채점 안 함)
  E-->>E: hit@3 · hit@1 → retrieval_eval_latest.json
  E->>A: /rag/eval runs 기록 (임베딩 모델별)
  A-->>D: 정확도 카드 (hit@3 92% · hit@1 77%) · 채택 모델
  Note over C: manifest.active_collection 이 가리키는 컬렉션을 /fix 가 사용
```

---

## 6. 어디가 RAG인가 (한 장 요약)

```mermaid
flowchart TB
  subgraph RAGyes["RAG (검색 필요 · 라벨 없음)"]
    F["/fix: 학생 문장 → 규칙 조각"]
    Q["/ask: 학생 질문 → 설명 조각"]
  end
  subgraph RAGno["DB 조회 (id 있음 · 검색 불필요)"]
    N["/notebook: 학생 → 규칙 목록"]
    P["/patterns · /words: Unit → 카드"]
    R["/drill: rule_id → 오류 예시"]
    T["/tts/{id}: id → 음원"]
  end
  RAGyes -.->|근거 조각 id 로 연결| RAGno
  classDef y fill:#FBF0DC,stroke:#E8A33D,stroke-width:2px,color:#1F2823
  classDef n fill:#E4EFEA,stroke:#14554A,color:#1F2823
  class F,Q y
  class N,P,R,T n
```
