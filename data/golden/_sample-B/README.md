# 골든 데이터 샘플 B — 컬럼 정의 + 예시 몇 줄

plan-B(내 문장 고쳐주기 튜터)용. 데이터팀은 **이 형식 그대로 채워서** `data/golden/` 에 납품한다.
파일 7개. 우선순위: ① rules.jsonl + eval.csv (RAG 실험) → ② units · patterns · words (화면) → ③ errors.jsonl (규칙 연습) → ④ faq.jsonl (물어보기 챗)

**임베딩(Chroma 색인) 대상은 rules.jsonl 하나 (나중에 faq.jsonl 은 별도 컬렉션).** eval.csv 는 시험지라 색인에 넣지 않고, 검색이 맞는지 채점할 때만 쓴다. errors · patterns · words · units 도 색인 대상이 아니다.

| 파일 | 한 줄 = | 임베딩 | 컬럼 | 목표량 |
|---|---|---|---|---|
| `rules.jsonl` ★ | 규칙 설명 조각 (RAG 검색 대상) | **O** (컬렉션 rules) | id · type · unit · text · short · examples · wrong_example | 25 |
| `eval.csv` | 평가: 학생 문장 → 정답 규칙 | **X** 시험지. 검색 채점(hit@3)에만 | text · expected_rule_id · note | 30 (정상 문장 5 = NONE) |
| `units.csv` | Unit = 말하기 미션 | X | level · unit · title · mission · hint_words · rule_ids | 3 |
| `words.csv` | 단어 | X | id · level · unit · word · meaning · example | 40 |
| `patterns.csv` | 문장 패턴 | X | id · level · unit · text · meaning · tip · rule_id | 20 |
| `errors.jsonl` | 오류 예시 (연습·데모) | X 규칙 연습 문제 | id · unit · rule_id · error · correct · target · fix · distractors | 40 |
| `faq.jsonl` | 물어보기 챗 질문·답 조각 (RAG 검색 대상) | O 나중에 (컬렉션 explain, /ask 용) | id · unit · question · variants · answer · rule_ids · example | 30 |

## faq.jsonl 한 줄 해설 — 물어보기 챗의 "교재"

학생이 🙋 물어보기 챗에 던지는 질문에 답할 때 RAG가 검색하는 조각. rules.jsonl 이 "규칙 설명"이라면 faq.jsonl 은 "질문에 대한 답".

```
{"id":"F-01",                        F-번호
 "unit":"U3",                        주로 나오는 Unit. 어디서나 물을 법하면 "ALL"
 "question":"왜 went예요?",           대표 질문 (챗의 '추천 질문' 버튼에 그대로 씀)
 "variants":["go 과거가 뭐예요",      같은 뜻의 다른 표현들. 검색 본문에 함께 넣어 "삐뚤빼뚤한 질문"도 잡히게 (깔때기)
             "갔다를 영어로 뭐라고 해요"],
 "answer":"go의 과거형은 규칙 없이…", 초등 3학년 말투 2~3문장. 이 밖의 내용은 챗이 말하지 않음 (목줄)
 "rule_ids":["R-01"],                근거 규칙. 답 밑에 📚 로 표시. 규칙과 무관한 단어 질문이면 []
 "example":"I went to the zoo yesterday."}   예문 1개 (선택)
```

쓰는 법
- **question 은 아이 말투로.** "과거형 불규칙 동사의 활용은?" ✕ → "왜 went예요?" ○
- **variants 3개 이상.** 같은 질문을 다르게 묻는 방식. 이게 많을수록 검색이 잘 됨
- 답은 rules 의 내용과 어긋나면 안 됨 (rule_ids 로 연결해 검수)
- 30개 구성 안: 규칙 질문 15 · 단어 뜻 질문 10 · "다른 예문 보여줘" 같은 요청 5
- 데이터팀 샘플의 `feedback` 이 출발점 — 규칙별로 자주 나오는 질문을 뽑아 정리

## 규칙

- **id 형식**: 규칙 `R-01`, 단어 `w-0001`, 패턴 `p-0001`, 오류 `E-0001`. 중복 금지
- **rule_id 참조**: units · patterns · errors · eval 의 rule_id 는 rules.jsonl 에 있는 id 만
- **eval.csv 의 text 는 rules.jsonl 의 wrong_example · errors.jsonl 의 error 와 겹치면 안 됨** (시험지가 교과서에 있으면 점수가 의미 없음)
- 인코딩 UTF-8 · csv 는 쉼표 · 값에 쉼표가 있으면 큰따옴표로 감쌈 · jsonl 은 한 줄에 JSON 하나
- 검색이 잘 되는 rules 텍스트 쓰는 법: [docs/plan-B/data-pipeline-plan.md](../../../docs/plan-B/data-pipeline-plan.md) 4절

## rules.jsonl 한 줄 해설

```
{"id":"R-01",                         규칙 id
 "type":"과거시제",                    오류 유형 이름 (6개 중 하나)
 "unit":"U3",                         주로 쓰이는 Unit (여러 Unit이면 "ALL")
 "text":"어제(yesterday)… 틀린 예: …", RAG 검색용 본문 80~200자. 학생이 쓸 법한 영어 단어 + 맞는 예 2 + 틀린 예 1 + 한국어 설명
 "short":"과거를 말할 땐 동사를 과거형으로",  패턴 카드 힌트 한 줄
 "examples":["I went …","I saw …"],   맞는 예문 (연습 해설·듣기)
 "wrong_example":"I go to the zoo yesterday."}   틀린 예 1개 (연습 문제 재료)
```
