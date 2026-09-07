# 골든 데이터 샘플 B — 컬럼 정의 + 예시 몇 줄

plan-B(내 문장 고쳐주기 튜터)용. 데이터팀은 **이 형식 그대로 채워서** `data/golden/` 에 납품한다.
파일 6개. 우선순위: ① rules.jsonl + eval.csv (RAG 실험) → ② units · patterns · words (화면) → ③ errors.jsonl (규칙 연습)

| 파일 | 한 줄 = | 컬럼 | 목표량 |
|---|---|---|---|
| `rules.jsonl` ★ | 규칙 설명 조각 (RAG 검색 대상) | id · type · unit · text · short · examples · wrong_example | 25 |
| `eval.csv` | 평가: 학생 문장 → 정답 규칙 | text · expected_rule_id · note | 30 (정상 문장 5 = NONE) |
| `units.csv` | Unit = 말하기 미션 | level · unit · title · mission · hint_words · rule_ids | 3 |
| `words.csv` | 단어 | id · level · unit · word · meaning · example | 40 |
| `patterns.csv` | 문장 패턴 | id · level · unit · text · meaning · tip · rule_id | 20 |
| `errors.jsonl` | 오류 예시 (연습·데모) | id · unit · rule_id · error · correct · target · fix · distractors | 40 |

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
