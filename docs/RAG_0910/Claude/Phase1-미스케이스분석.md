# Phase 1 — hit@1 미스 케이스 원인 분석

작성일: 2026-09-10
근거: `data/rag_eval/retrieval_eval_latest.json` (실데이터 38규칙, `all-MiniLM-L6-v2`, evaluated_at 2026-09-09T14:27:37, hit@1=70.77%, hit@3=87.69%, n=65)
관련 계획: [RAG_작업방향.md](RAG_작업방향.md) §0 회의 목표, Phase 1

---

## 요약

오류 문장 65건 중 **hit@1 미스 19건(29.2%)**을 전부 검토했습니다.

| 그룹 | 건수 | 정의 |
|---|---|---|
| C — 순위 역전 | 11건 | 정답이 top-3엔 있지만 1위가 아님 |
| A — 완전 미스 | 8건 | 정답이 top-3에도 없음 |

당초 계획한 (a)표면겹침/(b)규칙부재/(c)순위역전 3분류 대신, 실제 데이터를 보니 **4가지 구체적 패턴**으로 나뉘었습니다.

---

## 패턴 ① R-01(형용사+be동사)이 자기 오류 유형에서 전혀 검색되지 않음 — 가장 심각

| 문장 | 기대 규칙 | top-3 (실제 뽑힌 것) |
|---|---|---|
| "He tired after school." | R-01 형용사+be동사 | R-22(빈도부사 어순), R-18(소유격+신체부위), R-28(too+형용사) |
| "He hungry now." | R-01 형용사+be동사 | R-32(3인칭단수), R-38(관사), R-10(want+명사) |

R-01 예문("I am sorry.", "She is polite.")이 tired/hungry 같은 실제 형용사와 임베딩 유사도가 낮은 것으로 보입니다. "형용사만 쓰고 be동사를 빠뜨리는" 아주 기본적인 오류 유형인데도 **2건 모두 top-3 밖으로 완전히 빠짐** — 구조적 사각지대로 판단됩니다.

## 패턴 ② R-08 ⟷ R-12 반복 혼동 (단수/복수 일치 규칙끼리)

| 문장 | 기대 규칙 | top1로 뽑힌 규칙 |
|---|---|---|
| "These book are new." | R-08 This·These 단수복수 일치 | R-12 숫자+복수명사 일치 |
| "These apple are fresh." | R-08 This·These 단수복수 일치 | R-12 숫자+복수명사 일치 |

두 규칙이 개념적으로 인접(둘 다 단/복수 일치)해서 임베딩이 구분하지 못합니다. **동일 패턴이 2건 모두 재현** — 우연이 아니라 두 규칙 임베딩이 실제로 가까운 것으로 보입니다.

## 패턴 ③ 규칙 자체의 개념 중복 — 검색 문제가 아니라 데이터 설계 이슈

| 문장 | 기대 규칙 | 실제 2위 후보 |
|---|---|---|
| "She is eat lunch now." | R-35 현재진행형(전체) | R-17 현재진행형(옷 착용 특수) |

R-35(전체)와 R-17(옷 착용 한정)은 실제로 겹치는 개념입니다. 이런 경우는 임베딩·모델을 바꿔도 근본적으로 해결되지 않을 가능성이 높고, **규칙 체계 자체를 데이터팀과 재검토**하는 게 맞는 방향으로 보입니다. (참고: "That is rainy today." → R-14 vs top1 R-15도 같은 유형 — 둘 다 Unit08의 날씨/미래 인접 규칙)

## 패턴 ④ 뚜렷한 어휘 겹침으로 인한 오탐 (점수 갭 큼, 확신도 높은 오답)

| 문장 | 기대 규칙 | top1(오답) | 겹치는 표현 | 점수 갭 |
|---|---|---|---|---|
| "We are at the park yesterday." | R-37 과거시제 | R-24 go to the+장소 | "the park" | 0.226 |
| "She wants many bread." | R-09 셀 수 없는 명사 | R-10 want+명사 | **"want"**(규칙명 자체와 겹침) | 0.161 |
| "There are a cat under the table." | R-05 There is·are 구문 | R-30 위치전치사 in·on·under | "under the table" | 확신도 매우 높음(top1 점수 0.50) |

문장에 포함된 단어가 다른 규칙의 예문/이름과 그대로 겹쳐서 발생. 갭이 크고 확신도가 높다는 게 특징 — 단순 순위 조정보다 임베딩 구성 자체를 바꿔야 해결될 가능성.

## 그 외 — 거의 동점(gap < 0.03), 사실상 랜덤 5건

| 문장 | 기대 | top1 | 갭 |
|---|---|---|---|
| "We swim at summer." | R-16 | R-19 | 0.0005 |
| "He goes to work by a bike." | R-23 | R-26 | 0.0034 |
| "I saw a house big." | R-11 | R-08 | 0.021 |
| "My sister like cats." | R-32 | R-33 | 0.024 |
| "He is scared about the dog." | R-27 | R-33 | 0.037 |

**Top-K를 5로 넓히면 자연스럽게 해결될 가능성이 높은 그룹** — Phase 2-1에서 바로 검증.

---

## Phase 2 우선순위에 주는 시사점

- **패턴①·④** → "예시문 포함 임베딩"(2-2)이나 "모델 재테스트"(2-3)로 개선 여지가 큼
- **패턴②** → 두 규칙(R-08/R-12, R-35/R-17)에 서로 구분되는 신호(오답 예문 등)를 추가하면 도움될 것으로 예상
- **패턴③** → 검색 알고리즘 문제가 아니라 **규칙 정의 자체의 중복** — 별도로 데이터팀 논의 필요, Phase 2 실험 대상에서 제외
- **근소한 차이 5건** → k=5 비교로 즉시 검증 가능 (Phase 2-1)

---

## 전체 미스 목록 (원자료)

### Group C — 순위 역전 (11건)

| 문장 | 기대 | 실제순위 | 1위 | 갭 |
|---|---|---|---|---|
| My sister like cats. | R-32 | 2위 | R-33 | 0.024 |
| We are at the park yesterday. | R-37 | 3위 | R-24 | 0.226 |
| He is worried of his dog. | R-27 | 3위 | R-33 | 0.044 |
| That is rainy today. | R-14 | 2위 | R-15 | 0.094 |
| We swim at summer. | R-16 | 2위 | R-19 | 0.0005 |
| She enjoys to read. | R-20 | 2위 | R-06 | 0.079 |
| That is my dog toy. | R-03 | 3위 | R-33 | 0.059 |
| She wants many bread. | R-09 | 3위 | R-10 | 0.161 |
| I saw a house big. | R-11 | 2위 | R-08 | 0.021 |
| He goes to work by a bike. | R-23 | 2위 | R-26 | 0.0034 |
| He is scared about the dog. | R-27 | 2위 | R-33 | 0.037 |

### Group A — 완전 미스 (8건)

| 문장 | 기대 | top-3 |
|---|---|---|
| She is eat lunch now. | R-35 | R-38, R-17, R-32 |
| I have dog. | R-38 | R-33, R-32, R-30 |
| He tired after school. | R-01 | R-22, R-18, R-28 |
| There is many pencils in the box. | R-05 | R-20, R-12, R-30 |
| These book are new. | R-08 | R-12, R-06, R-30 |
| He hungry now. | R-01 | R-32, R-38, R-10 |
| There are a cat under the table. | R-05 | R-30, R-33, R-32 |
| These apple are fresh. | R-08 | R-12, R-11, R-38 |
