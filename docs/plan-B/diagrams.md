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
    STT[["Gemini STT"]]
    TTS[["Gemini TTS"]]
    RAG[["RAG 검색<br/>Chroma"]]
    LLM[["Gemini 생성"]]
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
| 더 물어보기 | 학생 | 설명 조각 검색(RAG) · 생성 | 추천 질문 버튼 / 직접 입력 |
| 규칙 연습 | 학생 | 문제 꺼내기(DB) · 채점 · streak | 2회 연속 정답 → 극복 |
| 골든 데이터 납품 | 데이터팀 | 형식 검증 · 임베딩 · 조립 실험 | |

---

## 2. 시퀀스 다이어그램 ① 고쳐주기 (핵심 · `/fix`)

```mermaid
sequenceDiagram
  autonumber
  actor S as 학생
  participant UI as tutor.html
  participant SP as speak.py<br/>(STT)
  participant TU as tutor.py<br/>(/fix)
  participant RG as rag.py<br/>(Chroma)
  participant GM as Gemini
  participant ST as student.py<br/>(학생 DB)

  S->>UI: 🎙 말하기 (최대 6초)
  UI->>SP: POST /speak {audio_base64}
  SP->>GM: 오디오 첨부 + "받아 적어"
  GM-->>SP: "I go to the zoo yesterday"
  SP-->>UI: {heard}
  UI-->>S: 들린 문장 표시 · [고쳐줘]

  S->>UI: 고쳐줘
  UI->>TU: POST /fix {student, unit, text, source:"stt"}
  Note over UI: 화면: ① 문장 받기 ✓

  TU->>RG: search(text, kind=rule, k=3)
  Note over RG: 문장 임베딩 → 규칙 조각과 거리 비교<br/>프롬프트 없음
  RG-->>TU: [{R-01 과거시제 0.91}, {R-03 관사 0.42}, ...], threshold 0.60
  Note over UI: 화면: ② RAG 규칙 검색 ✓

  alt 1위 score ≥ threshold (규칙에 걸림)
    TU->>GM: prompts/fix.txt {sentence, rule_text(R-01)} · JSON 강제
    GM-->>TU: {ok:false, wrong:"go", fix:"went", fixed:"I went…", why:"…"}
    TU->>ST: 오답노트 기록 (R-01 count+1, streak 0) + 문장 로그
  else 1위 score < threshold (걸리는 규칙 없음)
    TU->>GM: fix.txt {sentence, rule_text: 없음}
    GM-->>TU: {ok:true, why:"문법에 맞는 문장이에요"}
    TU->>ST: 문장 로그만
  end
  Note over UI: 화면: ③ AI 설명 ✓

  TU-->>UI: {ok, rule, runner_up, wrong, fix, fixed, why, source, suggested_questions, log_id}
  UI-->>S: 진단 카드 · 근거(R-01 · 0.91) · 🔊 · 더 물어보기 버튼 3개

  opt 검색 실패 · 30초 초과
    TU->>GM: prompts/fix_fallback.txt {sentence, all_rules(≤30)}
    Note over TU: mode:"fallback" — RAG 없이도 동작
  end
```

---

## 3. 시퀀스 다이어그램 ② 더 물어보기 (`/ask`)

```mermaid
sequenceDiagram
  autonumber
  actor S as 학생
  participant UI as tutor.html
  participant TU as tutor.py<br/>(/ask)
  participant RG as rag.py<br/>(Chroma)
  participant GM as Gemini
  participant ST as student.py

  S->>UI: "왜 went예요?" (추천 버튼 또는 직접 입력)
  UI->>TU: POST /ask {student, log_id, question}
  TU->>ST: log_id 로 직전 진단 읽기 (문장 · 규칙 · 고친 문장)
  ST-->>TU: last_diagnosis
  TU->>RG: search(question, kind=all, k=3)
  Note over RG: 규칙 조각 + 설명(FAQ) 조각에서 검색
  RG-->>TU: [{R-01 0.88}, {R-05 불규칙동사 0.81}, {P-… 0.40}]
  TU->>GM: prompts/ask.txt {question, chunks(≥threshold), last_diagnosis}
  GM-->>TU: "go의 과거형은 규칙 없이 went로…"
  TU-->>UI: {answer, source:[R-01, R-05]}
  UI-->>S: 답 + 📚 근거 id
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
  participant V as tests/validate.py<br/>(RAG 담당)
  participant B as tests/build_index.py
  participant C as Chroma<br/>(data/chroma/)
  participant E as tests/eval_rag.py
  participant A as admin.html

  D->>G: rules.jsonl · errors · eval · patterns · words 납품 (7일차)
  V->>G: 형식 검증 (컬럼 · id 중복 · rule_id 참조)
  V-->>D: 오류 목록 (있으면 수정 요청)
  loop 조립 방식 3종 (규칙만 / +예시 / +한국어)
    B->>G: rules.jsonl 읽기
    B->>C: text 조립 → 임베딩(Gemini Embedding, 조각당 1회) → 컬렉션 rules_X
  end
  E->>C: eval.csv 30문장 각각 search(k=3)
  E-->>E: hit@3 · hit@1 · 정상 문장 오탐률 · threshold 후보
  E->>A: /rag/eval runs 기록
  A-->>D: 정확도 그래프 (63 → 77 → 87) · 채택 방식
  Note over C: 채택된 컬렉션을 rules 로 지정 → /fix 가 사용
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
