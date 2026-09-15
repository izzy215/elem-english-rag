# Golden 데이터 mismatch 및 factcheck 결과

- 작성일: 2026-09-16
- 대상: `data/golden` 바로 아래의 CSV·JSONL 7개 파일
- 목적: 팀 내 데이터 수정 우선순위 합의 및 `/ask`·`/fix` 일괄평가의 정답 기준 정비
- 상태: 읽기 전용 검사 결과. 원본 데이터 수정, 재색인, LLM 재평가는 수행하지 않음
- 기준: 검사 당시 로컬 파일. GitHub 원격 최신 상태와 동일하다는 보장은 없음

## 1. 핵심 결론

**파일 형식과 규칙 ID 연결에는 문제가 발견되지 않았지만, 문법 설명·오답 라벨·정답 보기에는 실제 내용 오류가 있다.**

현재 데이터를 그대로 평가 정답으로 사용하면 올바른 모델 응답을 오답으로 판정하거나, 잘못된 설명을 재현한 응답에 높은 점수를 줄 수 있다. 따라서 검색 문턱값이나 프롬프트를 조정하기 전에 정답 데이터부터 정비해야 한다.

검사 결과는 다음 세 가지로 구분한다.

| 구분 | 의미 | 처리 원칙 |
|---|---|---|
| 확정 오류 | 데이터 설명이 사실과 다르거나 인정되는 정상 표현을 오답으로 지정 | 관련 파일을 함께 수정 |
| 정책·문맥 확인 | 단일 정답을 확정하려면 학습 목표, 문맥, 영어 변종 등의 조건이 필요 | 정책을 명시한 뒤 라벨 결정 |
| 평가 위험 | 형식 오류는 없지만 중복·유사 문장 등이 평가를 왜곡할 가능성 | 회귀용과 독립 평가용을 분리 |

**구조 검사는 전수 검사다. 내용 검토는 아래에 근거가 명시된 발견 사항을 보고하며, 나머지 모든 문장이 정확하다는 인증은 아니다. 전체 의미 정확도는 산출하지 않았다.**

## 2. 검사 범위 및 파일 현황

총 1,947개 레코드이며 CSV 헤더는 레코드 수에 포함하지 않는다. `_sample`, `_sample-B`, 학생 기록 및 실행 로그는 이번 7개 파일 범위에서 제외한다.

| 파일 | 레코드 수 | 역할 | 결과 요약 |
|---|---:|---|---|
| [rules.jsonl](../../data/golden/rules.jsonl) | 100 | 규칙 설명·예문·틀린 예문 | ID 정상. 잘못된 설명 및 정상 문장의 오답 지정 발견 |
| [errors.jsonl](../../data/golden/errors.jsonl) | 400 | 오류 문장·교정·선택지 | 치환 결과 정상. 정상 표현이 오답 보기에 포함된 사례 발견 |
| [faq.jsonl](../../data/golden/faq.jsonl) | 130 | 질문·변형 질문·답변 | 규칙 참조 정상. 내용 오류 및 질문–답변 범위 불일치 발견 |
| [units.csv](../../data/golden/units.csv) | 80 | 학년·유닛·미션·힌트·규칙 목록 | 학년·유닛 키 중복 없음. 패턴 규칙과의 포함 관계는 정책 확인 필요 |
| [patterns.csv](../../data/golden/patterns.csv) | 477 | 교과서 표현·번역·규칙 | 규칙 참조 정상. 유닛 규칙 목록에 직접 포함되지 않은 패턴 95건 |
| [words.csv](../../data/golden/words.csv) | 400 | 단어·뜻·예문 | ID 정상. 단어 뜻과 예문의 의미가 일치하지 않는 사례 발견 |
| [eval.csv](../../data/golden/eval.csv) | 360 | 평가 문장·기대 규칙 | 오류 라벨 300건, 정상 라벨 `NONE` 60건. 정상으로 인정 가능한 문장에 오류 라벨 존재 |

## 3. 구조 및 교차 파일 검사

### 3.1 확인된 정상 항목

| 검사 항목 | 방법 | 결과 |
|---|---|---|
| JSONL 파싱 | 각 레코드를 JSON으로 파싱 | 파싱 오류 없음 |
| CSV 형식 | 인용부호를 인식하는 CSV 파서로 읽고 헤더 대비 열 개수 비교 | 열 개수 오류 없음 |
| ID 중복 | rules·errors·faq·patterns·words에서 파일별 ID 비교 | 중복 없음 |
| 유닛 키 중복 | units의 `(level, unit)` 조합 비교 | 중복 없음 |
| 규칙 참조 | errors·patterns·faq·units·rules.related·eval의 규칙 ID를 rules와 대조. eval의 `NONE` 제외 | 존재하지 않는 규칙 ID 0건 |
| 교정 치환 | 400건 모두 `error.Replace(target, fix)`와 `correct`를 대소문자까지 비교 | 불일치 0건 |
| 단어–패턴 예문 | `w-NNNN`과 `p-NNNN`을 대응시켜 `words.example`과 `patterns.text` 비교 | 400쌍 모두 일치 |

주의: `error → correct` 치환이 일치하는 것은 데이터 내부의 문자열 연결이 맞다는 뜻이다. 원문이 실제 오류인지, 교정이 적절한지까지 검증한 것은 아니다. 단어와 패턴이 같은 잘못된 예문을 공유해도 예문 일치 검사는 통과한다.

### 3.2 mismatch 및 평가 위험 재검증

| 항목 | 실측값 | 판정 및 해석 |
|---|---:|---|
| 패턴 규칙이 해당 유닛 규칙 목록에 직접 없음 | 95건 | 목록 간 불일치. 95개 문장이 틀렸다는 뜻은 아님 |
| `unit=ALL`인 패턴 | 2건 | p-0461·p-0462. 유닛별 로더와 색인에서 포함 정책을 확인해야 함 |
| 서로 다른 FAQ에 동일 질문이 존재하는 그룹 | 4그룹 | 모두 내용 모순은 아님. 문맥 없는 단일 FAQ ID 채점은 위험 |
| 오류 평가 문장과 검색용 오류 문장의 정규화 후 완전 일치 | 0/300건 | 직접 중복은 발견되지 않음. 독립성이 보장되는 것은 아님 |
| 검색용 오류 문장과 한 토큰만 다른 오류 평가 문장 | 176/300건 | 템플릿 유사성 위험. 176건 모두 누수라고 확정할 수는 없음 |

검사 정의:

- **95건**: `patterns.unit != ALL`, 참조 규칙의 `rules.unit != ALL`인 패턴 중, 해당 `(level, unit)`의 `units.rule_ids`에 패턴의 `rule_id`가 없는 레코드 수다.
- **완전 일치 검사**: 소문자화, 앞뒤 공백 제거, 연속 공백 축약, 문장 끝 `. ! ?` 제거 후 비교했다. 비교 대상은 `errors.error`와 `rules.wrong_example`이다.
- **한 토큰 차이 검사**: 위 정규화 후 공백으로 토큰화했을 때 길이가 같고, 정확히 한 위치의 토큰만 다른 검색용 문장이 존재하는 평가 레코드를 센다. 유사 쌍의 총수가 아니라 평가 문장 수다.
- 위 정규화는 중복 탐지용이다. 문장부호 교정의 정오 채점에 그대로 적용하면 안 된다.

대표 목록 불일치:

| 위치 | 데이터 | 확인 사항 |
|---|---|---|
| patterns.csv 10행, p-0009 | 4학년 Unit01, `Please help me.`, R-45 | 같은 학년·유닛의 rules 목록에 R-45가 없음 |
| patterns.csv 13행, p-0012 | 5학년 Unit01, `Let's introduce ourselves.`, R-73 | 같은 학년·유닛의 rules 목록에 R-73이 없음 |
| patterns.csv 462행, p-0461 | 3학년 ALL, `I don't like snakes.`, R-99 | ALL 패턴의 유닛별 포함 정책 확인 필요 |
| patterns.csv 463행, p-0462 | 3학년 ALL, `Do you like pizza?`, R-100 | ALL 패턴의 유닛별 포함 정책 확인 필요 |

FAQ 중복 그룹:

| 정규화된 질문 | FAQ ID | 주의점 |
|---|---|---|
| 다른 예문 알려줘요 | F-22, F-23, F-24, F-25, F-64, F-65, F-66, F-67, F-68 | 직전 학습 규칙 등 대화 문맥이 필요 |
| 지금 하는 중이라는 걸 어떻게 말해요 | F-08, F-42 | 유사 규칙에 대한 답변일 수 있어 복수 정답 검토 필요 |
| next to가 뭐예요 | F-77, F-114 | 같은 표현을 다른 규칙 문서가 설명할 수 있음 |
| want to be랑 뭐가 달라요 | F-30, F-119 | 무엇과 비교하는지 문맥이 필요 |

## 4. 문법·의미 factcheck

아래 행 번호는 검사 당시 파일 기준이다. JSONL은 ID를 우선 식별자로 사용하고, eval은 문장과 기대 규칙을 함께 확인한다. 표의 개선 방향은 제안이며 아직 적용하지 않았다.

### 4.1 확정 오류 및 오답 라벨 문제

| 위치 | 현재 내용 | 판정 | 개선 방향·근거 |
|---|---|---|---|
| rules.jsonl 29행, R-29 | “가격을 물을 때 셀 수 있으면 How many” | 가격 질문과 수량 질문을 혼동한 설명 | 가격은 How much, 셀 수 있는 것의 개수는 How many로 구분. R-29의 short 및 F-40과 설명 통일. [S1](#s1) |
| rules.jsonl 46행, R-46 | `Whose is this pencil?`을 wrong_example로 지정 | 정상 구조를 오답으로 지정 | Whose + 명사 구조만 가능한 것으로 제한하지 않기. [S2](#s2) |
| eval.csv 38행 및 faq.jsonl 32행, F-32 | `He was first in line.` → R-13 / “서수 앞에는 항상 the” | 정상 표현의 오류 라벨 및 과도한 일반화 | 해당 평가 문장을 정상으로 재분류하거나 명백한 오류 문장으로 교체. R-13 연계 예문도 재검토. [S3](#s3) |
| errors.jsonl 131행, E-0131 | 정답 buses, 오답 보기 busses | 인정되는 복수 철자를 오답으로 지정 | 권장 철자와 허용 철자를 구분하고 busses를 오답 보기에서 제외. [S4](#s4) |
| errors.jsonl 5~8행, E-0005~E-0008 | 마침표 인사말을 오답 보기로 지정 | 느낌표가 필수라는 잘못된 전제 | R-02·F-26 및 오답 보기 동시 수정. 이름을 부르는 쉼표와 문장 끝 부호를 분리해서 설명. [S5](#s5) |
| rules.jsonl 67행, R-67 및 faq.jsonl 97행, F-97 | pants, shoes, socks, gloves는 항상 복수형 | pants와 단수형이 존재하는 일반 명사를 혼동 | shoe, sock, glove의 단수형을 인정하고 해당 주어의 실제 수에 따라 동사 일치 설명. words의 w-0190에도 glove가 존재. [S6](#s6) |
| faq.jsonl 6행, F-06 | “형용사는 우리말과 반대로 명사 앞에” | 한국어 어순 설명 오류 | 한국어도 ‘빨간 사과’처럼 수식어가 앞에 오므로 “우리말과 반대로” 삭제 |
| words.csv 11행, w-0010 | welcome=환영하다 / 예문 You're welcome. | 단어의 제시 뜻과 예문 속 용법 불일치 | 환영하다에 맞는 예문으로 바꾸거나 관용구 You're welcome.=천만에요를 별도 설명. p-0010의 번역은 천만에요로 맞음. [S7](#s7) |

### 4.2 문맥·정책·답변 범위 확인 사항

| 위치 | 현재 내용 | 문제 및 판단 조건 | 제안 |
|---|---|---|---|
| eval.csv 56행 | `I like dance.` → R-19 | dance는 명사 ‘무용’으로도 해석되므로 문맥 없이 틀렸다고 확정할 수 없음. [S8](#s8) | 명확한 동사 사용 오류로 교체하거나 문맥·허용 해석 제공 |
| rules.jsonl 45행, R-45 / errors E-0177~E-0180 / eval.csv 134행 등 | You가 있는 교실 지시문을 오류 처리 | You를 넣은 강조 명령문도 가능. R-45의 `You open your book.`은 평서문 해석도 가능. [S9](#s9) | 기본 명령문 형태 연습과 문법 오류 교정을 구분 |
| faq.jsonl 9행, F-09 | variant는 “like 뒤에 to를 써도 돼요?”인데 answer는 -ing만 설명 | 질문에 대한 핵심 답변 누락. R-19에는 -ing/to 두 형태가 이미 설명됨. [S10](#s10) | “to + 동사원형도 가능”을 답변에 명시 |
| errors.jsonl 273·275행, E-0273·E-0275 | have toothache를 have a toothache로 교정 | 영국 영어에서는 무관사 사용도 인정됨. 미국 영어 목표 형태와 일반 문법 오류를 구분해야 함. [S11](#s11) | 영어 변종 정책을 정하고 ‘다른 허용 표현’을 오답으로 처리하지 않기 |

미국 영어를 수업의 기본으로 삼더라도, 다른 표준 영어 표현을 ‘목표 표현과 다름’으로 안내할지 ‘문법 오류’로 평가할지는 별도 결정해야 한다.

## 5. 일괄평가에 미치는 영향

| 데이터 문제 | 발생 가능한 평가 왜곡 | 필요한 통제 |
|---|---|---|
| 정상 문장의 오류 라벨 | 모델이 문장을 유지하면 실패, 불필요하게 교정하면 성공 처리 | 정상 여부를 먼저 검수하고 애매한 항목 임시 제외 |
| 잘못된 FAQ 답변 | 잘못된 답변을 그대로 재현한 모델이 고득점 | FAQ 정답 설명 자체를 검수 |
| 허용 표현이 오답 보기에 존재 | 학습자가 정상 표현을 골라도 오답 처리 | 정답·오답 후보를 완성 문장으로 비교하고 복수 정답 여부 검수 |
| FAQ 질문 중복 | 내용이 맞아도 예상 FAQ ID와 다르다는 이유로 실패 | 답변 정확성과 출처 ID 일치를 별도 측정 |
| 템플릿 유사 평가 문장 | 검색 및 응답 성능이 새로운 학생 문장에 대한 성능보다 높게 나올 가능성 | 회귀용과 템플릿 독립 holdout을 분리 |
| 유닛 규칙 목록 불일치 | 정답 규칙의 자동 후보 주입 여부가 달라질 가능성 | 검색 결과·최종 후보·프롬프트 노출을 별도 기록 |

기존에 제공된 `/fix` 81/100 대 89/100, hit@3 90%·78%·91%는 기존 시험지·설정의 기준선이다. 이번 데이터 검사로 재측정한 수치가 아니며, 현재 eval 360건의 성능으로 해석하면 안 된다. 정답 라벨이 바뀌면 구·신 평가셋 버전을 구분해 보고해야 한다.

또한 CSV·JSONL 검사만으로 현재 실행 중인 서버의 `/ask` 정확도나 색인 최신성을 확인할 수는 없다. 정제 후 별도 실행 검증이 필요하다.

## 6. 실행 계획


| 순서 | 작업 | 제안 담당 | 완료 기준 |
|---:|---|---|---|
| 1 | 평가의 정상/오류 기준, 목표 영어 변종, 복수 정답 허용 정책 합의 | 교육·평가 담당 | 문법 오류와 권장 표현을 구분한 기준 확정 |
| 2 | 위 표의 규칙·FAQ 설명 및 오답 보기 정비 | 데이터 담당 + 문법 검수자 | R-29·R-46 등 관련 설명과 예문 사이에 모순이 없음 |
| 3 | 영향받는 errors·eval 동시 검수 | 평가 담당 | 정상 문장의 오답 라벨 제거, 애매한 항목 제외 또는 문맥 추가 |
| 4 | 유닛 규칙 목록 95건 및 ALL 2건 정책 확정 | 교육·백엔드 담당 | 직접 포함 의무 여부와 ALL 처리 계약 문서화 |
| 5 | 구조·참조·치환 검사 재실행 | 개발 담당 | 파싱, ID, 참조, 치환 검사 모두 통과 |
| 6 | 데이터 변경 후 재색인 | 백엔드 담당 | `python -m backend.textbook --rebuild` 성공 및 실제 색인 반영 확인 |
| 7 | 정제된 기준으로 `/ask`·`/fix` 일괄평가 | 평가·개발 담당 | 데이터·색인·모델·프롬프트 버전과 실패 원인이 함께 기록됨 |

### 수정 완료 체크리스트

- [ ] 확인된 설명 오류를 관련 규칙·FAQ·예문에서 함께 수정했다.
- [ ] 정답과 모든 오답 보기를 완성 문장 기준으로 검수했다.
- [ ] 정상으로 인정 가능한 eval 문장을 재분류하거나 교체했다.
- [ ] 질문 변형마다 FAQ 답변이 실제로 답하는지 확인했다.
- [ ] 95건 목록 불일치를 문장 오류와 구분해 처리했다.
- [ ] ALL 패턴을 유닛별 조회와 색인에서 어떻게 취급할지 결정했다.
- [ ] 한 토큰 차이 문장을 독립 성능 검증용으로 무비판적으로 사용하지 않았다.
- [ ] 데이터 정제 전후 평가셋 버전과 재색인 결과를 기록했다.

## 7. 문법 검증 근거

아래 자료는 대화 중 팩트체크에 사용한 사전·출판사·문법 자료다. 이 문서는 해당 근거와 로컬 데이터 검사 결과를 정리한 것이며, 외부 자료를 이용한 전체 데이터 자동 인증 결과는 아니다.

<a id="s1"></a>
1. **S1 — 가격과 How much**: [Cambridge Dictionary: How much](https://dictionary.cambridge.org/us/dictionary/english/how-much)

<a id="s2"></a>
2. **S2 — Whose의 독립 사용**: [Cambridge English Grammar Today: Whose](https://dictionary.cambridge.org/grammar/british-grammar/whose)

<a id="s3"></a>
3. **S3 — 관사 없는 first in line**: [Cambridge Dictionary: First in line](https://dictionary.cambridge.org/dictionary/english/first-in-line)

<a id="s4"></a>
4. **S4 — buses / busses**: [Merriam-Webster: Bus](https://www.merriam-webster.com/dictionary/bus)

<a id="s5"></a>
5. **S5 — 마침표로 끝나는 인사말**: [Cambridge University Press: Four Corners Level 1 발췌, 교재 8쪽](https://assets.cambridge.org/97811086/59611/excerpt/9781108659611_excerpt.pdf)

<a id="s6"></a>
6. **S6 — 단수형 옷·신발 명사**: [Merriam-Webster: Shoe](https://www.merriam-webster.com/dictionary/shoe), [Sock](https://www.merriam-webster.com/dictionary/sock), [Glove](https://www.merriam-webster.com/dictionary/glove)

<a id="s7"></a>
7. **S7 — You're welcome의 의미**: [Cambridge Dictionary: You're welcome](https://dictionary.cambridge.org/us/dictionary/english/you-re-welcome)

<a id="s8"></a>
8. **S8 — Dance의 명사 용법**: [Cambridge Dictionary: Dance](https://dictionary.cambridge.org/dictionary/english/dance)

<a id="s9"></a>
9. **S9 — You가 있는 명령문**: [Cambridge English Grammar Today: Imperative clauses](https://dictionary.cambridge.org/uk/grammar/british-grammar/imperative)

<a id="s10"></a>
10. **S10 — Like + -ing / to부정사**: [Cambridge English Grammar Today: Hate, like, love and prefer](https://dictionary.cambridge.org/us/grammar/british-grammar/hate-like-love-and-prefer)

<a id="s11"></a>
11. **S11 — Toothache의 가산·불가산 용법**: [Cambridge Dictionary: Toothache](https://dictionary.cambridge.org/dictionary/english/toothache)
