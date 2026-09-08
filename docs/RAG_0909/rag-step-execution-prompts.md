# RAG 단계별 실행·검증 프롬프트

이 문서만 열어 아래 프롬프트를 순서대로 복사하여 사용한다. 개발 요구사항은 기존 work order를 참조하고 여기서 중복 정의하지 않는다. work order는 무엇을 만들지 정하는 작업지시서이고, 이 문서는 단계 실행과 완료 판정을 요청하는 진행용 문서다.

현재 요구사항 기준: [팩트 점검 반영 work order v0.2](rag-implementation-work-order_v0.2.md). (2026-09-09부터 이 문서와 같은 폴더 `docs/RAG_0909/`에 있음 — 이전에는 한 단계 상위 `docs/`에 있었음)
최종 저장 예정 위치: `docs/plan-B/rag-implementation-work-order.md`. 현재 그 위치에는 이전 사본이 있으므로, 단순히 파일명만 보고 기준본을 바꾸지 않는다. 최종본으로 실제 교체한 뒤 위 링크와 아래 모든 복사용 프롬프트의 요구사항 기준 경로를 함께 변경한다.

## 사용 순서

1. 최초 실행 프롬프트로 ①을 구현한다.
2. 공통 완료 검증 프롬프트로 ①의 증거를 확인한다.
3. 미통과 항목이 있으면 보완 프롬프트를 사용하고 다시 검증한다.
4. 기능·계약 필수 조건이 모두 통과하고 진행 결정이 진행 가능일 때 다음 단계 프롬프트를 사용한다. 품질 목표 미달은 명시적인 사용자 결정 후 조건부 진행할 수 있으나 목표 달성으로 기록하지 않는다.
5. ④까지 완료한 뒤 최종 통합 검증을 요청한다.

단계를 자동으로 한꺼번에 실행하지 않는다. 한 번 요청할 때 지정된 단계만 진행한다. 단계 안의 통상적인 수정·시험은 반복 승인 없이 수행한다. 다만 tutor.py·교정 프롬프트는 팀장만 수정한다. RAG 담당은 해당 파일을 읽고 계약을 제안하거나 시험할 수 있지만 직접 수정하지 않는다. 필수 조건이 미검증이면 완료로 표시하지 않는다. 외부 호출 없이 통과한 시험과 실제 모델·색인 연동 검증을 구분한다.

| 단계 | 실행 범위 | 완료 검증의 핵심 |
|---|---|---|
| ① | 현황·계약·데이터 검증 | 실제 데이터 검증, API·임베딩 설정 결정 기록 |
| ② | 색인·검색 | 실제 색인·검색, 재생성·재시작·실패 시 보존 |
| ③ | 검색 평가 | 실제 hit@1·hit@3, 분모·실패 기록, 평가 API |
| ④ | 연결 정보 인계 → 팀장 구현 → 공동 검증 | 인계 계약·팀장 변경 확인 후 근거·교정·기록 검증 |

### 단계별 검증 경계

- ①의 필수 검증은 데이터 검증과 API·임베딩 모델·차원·문서/질의 처리 방식 등 설정 결정 기록이다. 실제 모델 호출·색인 생성은 ②의 검증 대상이며 ①의 완료 조건으로 앞당기지 않는다.
- ①에서 모델·계약 자체가 미확정이면 부분 완료다. 모델·설정은 확정됐으나 접속 정보가 준비 중이면 ②의 실제 연동 선행 조건으로 명시한다. ②에서 독립적인 코드 작업은 가능하지만 실제 연동 없이 ②를 완료 처리하지 않는다.
- ②는 실제 선택한 임베딩 구현과 색인의 동작을 검증한다. 외부 서비스가 아닌 로컬 모델을 선택했다면 해당 실제 로컬 실행이 검증 대상이다. mock 시험만으로 실제 연동 통과를 대신하지 않는다.
- ③의 품질 목표와 기능·계약 필수 조건은 별도 판정한다. 목표 미달에 대한 진행 허용은 기능 실패·미검증을 면제하지 않는다.
- 아래 공통 검증·보완 프롬프트의 `[대상 단계]`는 실행 전에 ①·②·③·④ 중 하나로 바꾼다.

## 1. 최초 실행 — ① 현황·계약·데이터 검증

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: ① 현황·계약·데이터 검증
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

너는 C:\elem-english-rag 프로젝트의 RAG 담당 백엔드 개발자다.

요구사항 기준은 docs/RAG_0909/rag-implementation-work-order_v0.2.md다(2026-09-09부터 docs/RAG_0909/에 있음, 원래 docs/였음). 먼저 해당 문서와 프로젝트 Markdown 지침, 관련 실제 코드를 읽어라. docs/plan-B/rag-implementation-work-order.md는 현재 이전 사본이므로 혼동하지 마라. 문서 이동이 확인되면 내용이 동일한 최종 기준본의 경로를 기록한 뒤 사용하라.

이번에는 실행 단위 ①만 구현·검증하라. 화면 HTML·JS·CSS는 수정하지 마라. 다른 사람의 변경을 보존하고, 커밋·푸시·배포는 하지 마라.

현재 코드와 문서의 차이를 확인하고 실제 선택 데이터 폴더·규칙 수·평가 문장 수·정상 문장 수를 기록하라. 데이터의 형식·중복 ID·필수 필드·정답 ID 참조·평가 중복을 검증하고 외부 호출 없는 validate-only 경로를 구현하라. 기존 golden.py의 공통 데이터 선택 정책을 재사용하라.

검색 API의 현재 계약과 추가할 계약, 임베딩 제공자·모델·차원·문서/질의 처리 방식, 입력 범위와 k 상한을 결정 또는 확인 필요로 기록하라. 키를 출력하지 마라. 필요한 정보가 없으면 해당 사항만 질문하고 독립적인 검증 작업은 계속하라.

완료 후 이 진행 문서의 기록란에 변경 파일, 실행 명령, 실제 결과, 미검증 항목, 확정 계약을 기록하라. 미검증 필수 조건이 있으면 부분 완료로 보고하라. ②는 시작하지 마라.
```

## 2. 공통 완료 검증 — 매 단계 후 사용

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: [대상 단계] 완료 검증
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

지정한 단계의 완료 기준을 이전 완료 주장을 전제하지 말고 현재 증거로 재검토하라. 같은 작업자의 재검토이며 별도 검증자의 독립 검증을 보장하는 것은 아니다. 작업자의 완료 주장이나 체크 표시만으로 통과시키지 말고 현재 코드·변경 사항·시험 결과를 근거로 판단하라.

1. work order의 해당 단계 필수 조건을 빠짐없이 표로 정리하라.
2. 각 조건을 통과 / 실패 / 미검증으로 구분하고 코드 위치 또는 실제 실행 결과를 붙여라.
3. 기존 실행 증거가 현재 변경에 유효하면 재사용하라. 코드 변경·실패·증거 부족이 있는 항목만 필요한 검증을 실행하라.
4. mock 시험은 실제 외부 연동 성공의 증거로 대체하지 마라. 실행하지 못한 이유를 기록하라.
5. 화면 수정 여부, 기존 API 계약 유지, 다른 담당자 코드 변경 범위, 비밀값 노출 여부를 확인하라.
6. 정적 코드 사실, 신규 설계 결정, 실제 측정 결과를 구분하라.

출력 형식:
- 현재 단계와 종합 판정: 통과 / 부분 완료 / 실패
- 표: 완료 조건 | 판정 | 증거 | 남은 조치
- 변경 파일과 기존 계약에 미치는 영향
- 기능·계약 필수 조건 판정: 통과 / 부분 완료 / 실패
- 품질 목표 판정: 달성 / 미달 / 미측정 / 해당 없음
- 다음 단계 결정: 진행 가능 / 조건부 진행 가능 / 사용자 결정 대기 / 진행 불가 및 이유

기능·계약 필수 조건, 품질 목표, 다음 단계 진행 결정을 별도로 판정하라. 기능·계약 필수 조건에 실패·미검증이 있으면 진행 불가다. 기능·계약 조건을 모두 통과했어도 품질 목표 미달이면 목표 미달로 기록하고 진행 결정은 사용자 결정 대기로 둔다. 사용자가 한계를 수용하고 진행하도록 명시한 경우에만 조건부 진행 가능으로 기록하라. 이 결정은 목표 달성이나 필수 기능 검증 통과를 대신하지 않는다.

이 진행 문서의 해당 단계 기록을 갱신하고 종료하라. 이번 요청에서는 다음 단계 구현을 시작하지 마라.
```

## 3. 미통과 항목 보완 — 필요한 경우만 사용

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: [대상 단계] 미통과 항목 보완
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

방금 완료 검증에서 실패 또는 미검증으로 남은 항목을 처리하라. 현재 단계와 work order의 범위를 유지하고, 이미 통과한 부분은 필요한 영향 범위 외에는 다시 작성하지 마라.

RAG 담당 소유 코드의 수정 가능한 실패를 보완하고 관련 시험을 실행하라. tutor.py·교정 프롬프트 결함은 팀장에게 전달할 수정 사항으로 기록하고 직접 수정하지 마라. 팀장 수정 전에는 해당 검증을 미통과로 유지하라. 키·접속·사용자 결정 등 필수 정보 부족은 구체적으로 질문하고 미검증 상태로 유지하라. 기준을 낮추거나 시험을 삭제해서 통과시키지 마라.

보완 후 완료 조건 표와 이 진행 문서의 기록을 갱신하라. 다음 단계는 시작하지 마라.
```

## 4. 다음 실행 — ② 색인·검색 구현

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: ② 색인·검색 구현
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

같은 work order와 이 진행 문서의 ① 완료 기록을 기준으로 실행 단위 ②만 진행하라.

먼저 ① 필수 조건이 모두 통과했는지 확인하라. 계약·데이터·설정이 이후 변경되었으면 영향을 받는 조건부터 다시 확인하라. 필수 조건이 미통과이면 ②를 시작하지 말고 보완 항목을 보고하라.

확정한 임베딩 설정과 공통 로더를 사용해 영속 Chroma 색인, 안전한 재생성, 공통 search_rules(), 기존 /api/rag/search를 구현하라. query·chunks 및 기존 입력을 유지하고 신규 항목 계약을 명시하라. 화면은 수정하지 마라.

실제 규칙 색인과 질의 검색, 건수 일치, 점수·후보 정렬, 중복·삭제 반영, 재시작 후 재사용, 재생성 실패 시 기존 색인 보존, 입력 오류·색인 장애를 검증하라. 실제 외부 연동을 못 했다면 mock 통과와 구분해 미검증으로 남겨라.

변경 파일·실행 명령·시험 결과·색인 설정·확정 검색 계약을 이 진행 문서에 기록하고 완료 검증에 필요한 증거를 보고하라. ③과 /fix 연결은 시작하지 마라.
```

## 5. 다음 실행 — ③ 검색 평가

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: ③ 검색 평가
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

같은 work order와 ② 완료 검증 결과를 기준으로 실행 단위 ③만 진행하라. 선행 필수 조건의 통과와 결과 유효성을 확인한 뒤 시작하라.

golden.eval_set()을 사용하는 검색 평가 실행기와 저장 결과만 읽는 /api/rag/eval을 구현하라. 기존 n·hit_at_1·hit_at_3·runs를 유지하라. 기존 tests/eval_fix.py의 생성 모델 비교를 검색 평가로 사용하지 마라.

정답 규칙이 있는 문장을 분모로 hit@1·hit@3를 측정하고 NONE 문장은 분리하라. 검색 실패를 분모에서 조용히 제외하지 마라. 문장별 후보·점수·정답·실패 이유와 데이터·색인·모델 설정을 저장하라. 평가 API 조회가 외부 호출을 유발하지 않는지 확인하라.

실측 지표, 품질 목표 달성 여부, 실패 사례, 미측정 항목, 현재 색인과 평가 결과 일치 여부를 보고하고 이 진행 문서에 기록하라. 목표 미달이면 기능 완료와 품질 미달을 분리해 보고하고 다음 단계 진행 여부를 사용자에게 확인하라. 결과나 임계값을 임의 조작하지 마라.

정상 문장 오교정은 아직 미측정으로 남겨라. 이번에는 ④를 시작하지 마라.
```

## 6. 다음 실행 — ④ 연결 정보 인계·팀장 구현·통합 검증

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: ④-A 연결 정보 인계 및 팀장 구현 후 ④-C 통합 검증
먼저 두 문서와 ③의 완료 기록을 읽어라. 기능·계약 선행 조건을 확인하고 품질 목표 미달에 대해 사용자가 진행을 허용했다면 그 결정과 제한을 기록하라.

너는 RAG 담당이다. tutor.py와 교정 프롬프트는 팀장이 수정한다. 해당 파일이나 화면·ask.py·speak.py를 직접 수정하지 마라.

먼저 ④-A를 수행하라. 실제 구현된 search_rules의 import 경로·인자·반환 항목·정렬·점수 의미·임계값 처리·예외·시간 제한을 제공하라. /rag/search와 /rag/eval의 실제 호출 예시, /fix 필드 매핑, 정상 검색·검색 장애·근거 밖 ID 시험 사례를 기록하라. 팀장에게는 HTTP 재호출 대신 공통 함수를 직접 사용하는 연결 방법을 안내하라.

팀장이 구현해야 할 요구사항을 인계하라: 기존 golden.py·llm.generate_json() 유지, 1위 근거 선택과 후보 목록 보존, 실제 점수·차순위·출처·모드 구성, 검색 대체와 생성 백엔드 대체 구분, 출력·근거 검증, 검증 실패 기록 금지, 기록 없는 내부 교정 경로 제공. ok·more_errors·full_fixed의 판단 범위는 전달 근거로 제한됨을 명시하라.

인계 내용은 이 진행 문서에 기록하거나 API 인터페이스 정의서가 있으면 참조하라. 사용자 요청 없이 팀장에게 메시지를 보내지는 마라.

팀장 수정이 아직 반영되지 않았다면 “④-A 인계 완료·④-B 팀장 구현 대기”로 기록하고 종료하라. 이 상태를 ④ 전체 완료로 표시하지 마라. 대신 tutor.py를 구현하지 마라.

팀장 구현 완료가 전달된 뒤 이 프롬프트를 다시 실행하면, 인계를 중복 작성하지 말고 변경 코드와 계약을 확인한 뒤 ④-C를 수행하라. 실제 교정 경로를 기록 없는 내부 경로로 평가하고 정상 문장 오교정·생성 실패·검색 장애·학생 기록 보호·응답 호환을 검증하라. 같은 규칙과 다른 규칙의 복수 오류를 구분해 한계를 보고하라.

발견한 RAG 소유 코드의 결함은 보완하라. tutor.py·교정 프롬프트 결함은 팀장 수정 요청 사항으로 기록하고 수정 완료 후 재검증하라. 팀장 변경 또는 실제 실행 증거가 없으면 미검증으로 유지하라.

진행 문서에 인계 계약·팀장 변경 증거·실행 명령·검증 결과·미완료 사항을 기록하라. 화면까지 검증 완료했다고 보고하지 마라.
```

## 7. 최종 통합 검증

```text
진행 문서: C:\elem-english-rag\docs\RAG_0909\rag-step-execution-prompts.md
요구사항 기준: C:\elem-english-rag\docs\RAG_0909\rag-implementation-work-order_v0.2.md
대상 작업: ①~④ 최종 통합 검증
먼저 두 문서와 해당 단계 기록을 읽어라. 아래에서 이 진행 문서는 위의 진행 문서 경로를 뜻한다.

①~④의 최종 완료 여부를 work order와 현재 코드에 대조해 검증하라. ④-A 인계 완료만으로 전체 완료 처리하지 말고 팀장의 ④-B 구현과 ④-C 통합 검증 증거를 확인하라. tutor.py·교정 프롬프트는 직접 수정하지 마라. 새 기능은 추가하지 마라.

단계별 증거의 유효성과 기존 계약 유지를 확인하라. 서비스 실행 흐름은 색인 준비 → 검색 → /fix 교정이며, 검증 흐름은 평가셋 → 검색 평가·교정 평가다. 평가를 사용자 요청의 중간 처리 단계로 연결하지 마라. 최종 설정으로 두 흐름이 각각 동작하는지 확인하라. 변경 이후 무효가 된 시험만 다시 수행하라. 실제 외부 연동과 mock 시험, 목표와 실측, 완료와 미검증을 구분하라.

최종 보고:
1. 단계별 완료 조건과 통과·실패·미검증
2. 최종 API 입력·응답 예시 및 PRD와의 차이
3. 데이터 검증·색인·검색·평가 실행 방법
4. 실제 검색 지표·정상 문장 평가·생성 실패·응답 시간
5. 기록 보호·장애 처리 확인 결과
6. 남은 제한과 다른 담당자 인계 사항

이 진행 문서의 최종 판정과 기록을 갱신하라. 미검증 필수 조건이 남으면 전체 완료로 보고하지 마라. 커밋·푸시·배포는 하지 마라.
```

## 8. 진행 기록 — 작업자가 매 단계 갱신

| 단계 | 상태 | 기능·계약 판정 | 품질 목표 판정 | 진행 결정 | 증거·상세 기록 |
|---|---|---|---|---|---|
| ① | 완료 | 통과 | 해당 없음(품질 목표는 ③ 대상) | 진행 가능 | 아래 ① |
| ② | 완료 | 통과 | 해당 없음(품질 목표는 ③ 대상) | 진행 가능 | 아래 ② |
| ③ | 완료(평가) | 통과 | **미달 (hit@3 75% < 목표 80%)** | **사용자 결정 대기** | 아래 ③ |
| ④ | ④-A 완료 · ④-B 팀장 구현 대기 | ④-A 통과(인계) / ④-B·C 미검증 | 미측정(품질 미달 상태에서 사용자 조건부 진행 허용) | 조건부 진행 가능(④-A만) | 아래 ④ |

### ① 현황·계약·데이터 검증 기록

- 기준 코드·확인 시각: 2026-09-08, `git status --short` 기준 브랜치 `main`, 이 실행 전 작업트리에 코드 변경 없음(문서만 untracked)
- 변경 파일: 신규 `backend/indexing.py` (검증 전용, `--validate-only`만 구현. 임베딩·Chroma는 아직 없음)
- 확정 데이터·API·임베딩 설정: 아래 "설정 결정 기록" 표
- 완료 조건별 증거와 실행 명령:

**실행 명령과 실제 결과**
```
$ python -m backend.indexing --validate-only
[indexing] 데이터 폴더: C:\elem-english-rag\data\golden\_sample-B (샘플 사용: True)
[indexing] 규칙 8개 · 평가 10개 (오류 8 · 정상 2)
[indexing] 결과: 통과
```
외부 호출(임베딩·Gemini) 없음. `golden.py`의 기존 폴더 선택 정책(`data/golden/words.csv` 존재 여부)을 그대로 재사용했고, `data/golden/`에 실 데이터가 없어 `_sample-B`가 선택됨 — 문서 기록과 일치.

검증기 자체의 신뢰도 확인을 위해 임시 복사본에 결함 3종(중복 ID, 빈 `text`, 존재하지 않는 `expected_rule_id`)을 주입해 재실행 → 3건 모두 정확히 검출·`실패`로 판정됨을 확인(실 데이터는 건드리지 않음).

**데이터 검증 세부**
- `rules.jsonl` 8개: `id/type/unit/text` 전부 비어있지 않음, ID 중복 없음(R-01~R-08).
- `text` 길이: 88~179자 — data-pipeline-plan.md 4절의 80~200자 권고 범위 안.
- `eval.csv` 10행: 오류 8(각 R-01~R-08 1:1 대응) + 정상 2(`NONE`) = 문서 기록과 일치. 정답 ID 전부 `rules.jsonl`에 존재.
- `eval.csv`의 `text`가 `rules.jsonl.wrong_example` / `errors.jsonl.error`와 겹치는 사례 0건 (`_sample-B/README.md` 규칙 통과).
- 참고(오류 아님): `rules.jsonl`의 R-03(명사복수형)은 자신의 `unit` 필드가 `U3`이지만 `units.csv`에서는 U3이 아닌 U4의 `rule_ids`에만 들어있음. R-02도 유사하게 `unit=U3`이면서 U3·U4 양쪽 `rule_ids`에 걸쳐 있음. `rag-pipeline-analysis-stage-1.md`가 R-02 사례로 이미 지적한 것과 같은 패턴이며, 검증 실패 사유로 넣지 않고 참고 경고로만 남김(단원 필터를 강한 제한으로 걸지 않는다는 v0.2 방침과 일치).
- `rules.jsonl`의 `text`에는 이미 한국어 설명+예문+틀린 예가 포함되어 있음을 재확인 — `examples`/`wrong_example`을 검색 본문에 재첨부하지 않는다는 방침 그대로 유지.

**임베딩 제공자·모델 — 1차 확인 후 SDK 설치·재확인**
- `google-genai>=1.0`(requirements.txt 지정)을 실제로 설치(2.22.0)해 `Models.embed_content` 를 코드로 직접 검사함(문서 재인용이 아니라 설치된 패키지 소스를 inspect로 읽음):
  - 시그니처: `embed_content(model: str, contents=..., config: EmbedContentConfig | None)`
  - `EmbedContentConfig` 필드: `task_type`(문자열, 자유값 — SDK 타입상 enum 강제 없음), `output_dimensionality`, `title`, `mime_type` 등
  - 응답 `EmbedContentResponse.embeddings[i].values`(`list[float]`)로 벡터를 받음
  - → **SDK가 embed_content 를 지원한다는 사실은 코드로 확정.** 문서/질의 구분은 `task_type` 파라미터로 하는 것이 맞다(RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY 등 — SDK 타입은 자유 문자열이라 정확한 값 목록은 계정에서 실제로 받아들이는지로 검증해야 함).
- **실제 계정 호출은 끝내 확인하지 못함.** 이 환경에 `.env`도 없고 `GEMINI_API_KEY`가 될 만한 값이 셸 환경변수에도 없어, 어떤 모델명이 실제로 이 프로젝트 계정에서 동작하는지는 검증할 수 없었다. `.env.example`이 이미 "gemini-2.5-flash 가 신규 키에서 막혀 gemini-3.6-flash 로 교체"라고 적어둔 것처럼, 이 프로젝트는 모델 가용성이 계정마다 다를 수 있다는 전례가 있어 **모델명 하나를 임의로 확정하지 않았다.**
- 이를 위해 `backend/indexing.py`에 `--check-embedding` 커맨드를 새로 추가함: 후보 모델 3종(`text-embedding-004`, `gemini-embedding-001`, `gemini-embedding-2-preview`) × `task_type`(RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY) 조합을 실제로 호출해 성공/실패와 실제 벡터 차원을 그대로 출력한다. `--validate-only`와 분리된 별도 플래그라 데이터 검증 경로는 외부 호출과 섞이지 않는다.
- 이 환경에서 실행한 결과: `GEMINI_API_KEY 가 없어 임베딩 실제 호출을 확인할 수 없음` (exit 2) — 키가 없어 실행이 안전하게 조기 종료됨(예외로 죽지 않음).

**실제 계정 확인 (2026-09-08, `.env`에 `GEMINI_API_KEY` 추가된 뒤 재실행)**

`python -m backend.indexing --check-embedding` 실행 결과:

| 모델 | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | 차원 | 비고 |
|---|---|---|---|---|
| `text-embedding-004` | 실패 (404) | 실패 (404) | — | 이 계정/API 버전에서 `embedContent` 미지원 — SDK 예시에 있다고 실제로 되는 게 아님을 확인 |
| `gemini-embedding-001` | 성공 | 성공 | 3072 | 8개 배치 입력 정상 반환 확인 |
| `gemini-embedding-2-preview` | 성공(단건) | — | 3072 | **8개를 한 번에 넣으면 응답 embeddings가 1개만 옴** (배치 미지원 또는 다른 동작) — `embed_documents(texts: list[str])` 배치 계약에 안 맞아 이번 후보에서 제외 |

**실측 검색 성능 비교 (규칙 8개 색인, 오류문장 8개로 hit@1·hit@3, n=8이라 1건=12.5%p)**

| 임베딩 | 키 필요 | 비용 | hit@1 | hit@3 | 놓친 문장 |
|---|---|---|---|---|---|
| Chroma 기본(all-MiniLM-L6-v2, 영어전용, 로컬) | ✕ | 무료 | 50% (4/8) | 75% (6/8) | R-05(현재진행형), R-08(관사a) |
| 다국어 로컬(paraphrase-multilingual-MiniLM-L12-v2) | ✕ | 무료 | 50% (4/8) | 75% (6/8) | R-05, R-08 (로컬 기본과 동일) |
| **Gemini `gemini-embedding-001`** | ○ | API 과금 | 50% (4/8) | 75% (6/8) | R-04(관사an), R-08(관사a) — 놓친 문장 자체는 로컬과 다름 |

세 후보 모두 이 8문항 샘플에서는 **동일하게 hit@3 75%로 목표(80%) 미달**. 표본이 너무 작아(n=8) 어느 쪽이 "더 낫다"고 단정할 근거는 아니며, 데이터 정식 납품(25개) 후 재측정이 필요하다.

**최종 결정 (임베딩 제공자·모델) — 2026-09-09 사용자 결정으로 변경**
- 애초 이 기록은 `gemini-embedding-001`을 1순위로 제안했었으나, **사용자가 Chroma 기본 로컬 임베딩(all-MiniLM-L6-v2)으로 진행하도록 최종 결정**했다. 세 후보가 `_sample-B` 실측에서 성능 동률(hit@3 75%)이었던 데다, API 키·과금이 필요 없고 완전 오프라인으로 동작하는 쪽을 택함.
- 제공자: `chromadb`(`chromadb.utils.embedding_functions.DefaultEmbeddingFunction`) 확정
- 모델: **`all-MiniLM-L6-v2`** 확정. 차원 384. task_type 구분 없음(문서/질의 모두 같은 함수 사용).
- Gemini(`gemini-embedding-001`)·다국어 로컬 모델은 API 장애·품질 이슈 시 교체 후보로만 기록해 두고 이번엔 구현하지 않음 — `backend/embedding.py`의 임베딩 함수만 갈아끼우면 되도록 호출부(rag.py·indexing.py)는 구체 모델을 모르게 설계함.

**남은 미검증 항목**
- 이번 실측은 `_sample-B`(규칙 8·평가 8)로 한 것이며 데이터 정식 납품(25개) 후 같은 비교를 반드시 재실행해야 한다. 지금 수치를 최종 성능으로 보고하지 않는다.

**팀장 인계 사항 (수정은 팀장, 기록만 여기 남김)**
- `frontend/js/tutor.js:59` — `${r.rule.score ? ... : ''}` truthy 체크. 검색 점수가 정확히 `0`이면 화면에 표시 안 됨. 실제 검색이 붙기 전(현재 `rule.score`는 항상 `null`)에는 드러나지 않던 버그.
- `frontend/js/admin.js`(`runCheck`)가 `POST /api/rag/check`를 호출 중이나 PRD-B 4.2 RAG 명세에는 이 엔드포인트가 없음(간단기획서 1차 범위표에서도 제외 ✕). 현재 `rag.py`가 항상 `{"ok":true,"warnings":[]}`를 반환하는 스텁이라 화면은 "검사 항상 통과"로 보임 — 이번 범위에서 구현하지 않음, 정리 여부만 인계.
- `frontend/js/admin.js`(`submitSource`)가 `POST /api/sources`를 호출하나 백엔드에 해당 라우트가 없음(`main.py`에도 미등록). 화면이 이미 실패를 try/catch로 처리 중이라 신규 구현 불필요, 참고로만 인계.

### 설정 결정 기록 (이번 실행에서 확정)

| 항목 | 확정 내용 |
|---|---|
| 데이터 경로 | `golden.py`의 기존 선택 정책 그대로 사용. 별도 `RAG_DATA_DIR` 설정 도입하지 않음(색인·교정이 항상 같은 폴더를 보게 하기 위함) |
| 색인 경로 | `data/chroma` (이미 `.gitignore`에 등록되어 있음을 확인) |
| 평가 결과 경로 | `data/rag_eval` (이미 `.gitignore`에 등록되어 있음을 확인) |
| 검색 응답 계약 | v0.2 방침 유지 확정: 최상위 키 `query`/`chunks` 그대로, `q`/`level`/`k` 그대로(`level`은 필터 미적용 명시). `kind`(rule/explain/all)·`hits` 전환은 이번에 도입하지 않고 후속 계약 변경으로 남김 |
| threshold | 최초 기준선은 미설정. 응답에 `"threshold": null` 필드는 포함하되 값은 실제 점수 분포 확인 후 결정 |
| 후보 수 k | 기본 3 |
| 임베딩 제공자·모델 | **확정**: `google-genai` / `gemini-embedding-001` / 3072차원 / `task_type=RETRIEVAL_DOCUMENT`(문서)·`RETRIEVAL_QUERY`(질의). 실제 계정 호출로 검증 완료(위 "실제 계정 확인" 참고). `text-embedding-004`는 이 계정에서 404, `gemini-embedding-2-preview`는 배치 임베딩 미지원으로 제외 |
| k 상한 | 이번 실행에서 결정하지 않음 — 실제 반환 수는 저장 건수 이하로 제한한다는 방침만 유지, 숫자 상한은 ②에서 확정 |
- 미통과 항목·필요 정보:
- 종합 판정·다음 단계 전달:

### ② 색인·검색 기록

- 기준 코드·확인 시각: 2026-09-09, ① 완료 상태(임베딩 결정 포함) 기준
- 변경 파일: 신규 `backend/embedding.py`, `backend/indexing.py`(`build_index()`/`load_manifest()`/`--rebuild` 추가), `backend/rag.py`(`/rag/search` 실제 구현. `/rag/check`·`/rag/eval`은 스텁 그대로 유지, 손대지 않음)

**임베딩 함수 (`backend/embedding.py`)**
- `embed_documents(texts) -> list[list[float]]`, `embed_query(text) -> list[float]` — chromadb `DefaultEmbeddingFunction`(all-MiniLM-L6-v2)을 감싼 것. task_type 구분이 없는 모델이라 문서/질의가 내부적으로 같은 함수를 씀.

**색인 (`backend/indexing.build_index()`)**
- 컬렉션 이름을 매번 `rules_<타임스탬프>`로 새로 만들고, 임베딩·저장 건수가 원본과 일치함을 확인한 뒤에만 `data/chroma/manifest.json`을 원자적 교체(임시파일 쓰기 → `os.replace`)한다. 교체가 끝난 뒤에만 이전 `rules_*` 컬렉션을 삭제 — 실패 시 이전 manifest·컬렉션이 그대로 남아 서비스가 안 깨짐.
- manifest에 `active_collection`, `provider`, `model`, `dim`, `distance`, `text_version`, `count`, `data_hash`(id·text 기준 sha256), `generated_at` 기록.
- 거리 기준: 컬렉션 생성 시 `metadata={"hnsw:space":"cosine"}`로 코사인 명시. `score = round(1 - cosine_distance, 4)`.

**검색 (`backend/rag.search_rules()` / `GET /api/rag/search`)**
- 기존 계약 유지: 최상위 `query`/`chunks`, 입력 `q`/`level`(미사용, 필터 미적용 명시)/`k`. 추가: `threshold`(현재 `null`), `score_type`(`"cosine_similarity"`).
- 입력 검증: `q` 공백 제거 후 1~1000자 아니면 422. `k`는 1~10(현재 규칙 8개 기준 여유 있게 설정, 데이터 늘면 재검토) 아니면 422. 저장 건수(8)보다 큰 `k`를 요청해도 초과 반환하지 않고 저장 건수로 자동 캡.
- 색인 없음/컬렉션 접근 실패/검색 중 예외는 전부 503 + 기존 `{"detail":"..."}` 포맷으로 통일. API 조회 시 색인을 자동 생성하지 않음(로드만 함).

**완료 조건별 증거와 실행 명령**

```
$ python -m backend.indexing --rebuild      (1회차)
[indexing] 색인 생성 완료: {"active_collection": "rules_20260909_000158294204", "provider": "chromadb-default",
  "model": "all-MiniLM-L6-v2", "dim": 384, "distance": "cosine", "text_version": "rule.text_raw_v1",
  "count": 8, "data_hash": "sha256:c2be97937abf7848", "generated_at": "2026-09-09T00:01:58"}

$ python -m backend.indexing --rebuild      (2회차, 재생성 시 중복·잔존 검증)
[indexing] 색인 생성 완료: {"active_collection": "rules_20260909_000206684327", ...}
→ Chroma 컬렉션 목록 확인: rules_20260909_000206684327 만 존재(개수 8) — 이전 rules_20260909_000158... 는 삭제됨. 중복 없음.
```

- **재시작 후 재사용**: `--rebuild` 실행 프로세스와 완전히 별개의 새 Python 프로세스(`FastAPI TestClient`로 별도 스크립트)에서 `PersistentClient`로 다시 연결해 검색 성공 — 디스크 영속 확인.
- **실제 검색 API 시험** (`fastapi.testclient.TestClient`로 `backend.rag.router`만 마운트해 실제 엔드포인트 호출 — `backend.main`은 오디오 처리용 무관 의존성(`imageio_ffmpeg` 등) 미설치로 이 환경에서 통짜 기동이 안 돼, 라우터 단위로 실제 HTTP 계층까지 검증함):
  - `GET /api/rag/search?q=I go to the zoo yesterday&k=3` → `200`, 1위 `R-01`(과거시제, score 0.4367) — 정답과 일치
  - `GET /api/rag/search?q=She likes bananas.&k=3` (NONE 정상 문장) → `200`, 뚜렷한 1위 없이 낮은 점수대 — 오탐 임계값 없음이 정직하게 드러남(threshold 미설정 상태이므로 이 응답만으로 "정상"이라 단정하지 않음, ③에서 판단)
  - `q`가 공백만 → `422 {"detail":"q 는 공백 제거 후 1~1000자여야 함"}`
  - `k=999` → `422 {"detail":"k 는 1~10 사이여야 함"}`
  - `k=10`(저장 건수 8 초과 요청) → `200`, `chunks` 8개로 자동 캡 — 초과 반환 없음
  - **색인 없음 시뮬레이션**: `manifest.json`을 임시로 다른 이름으로 옮긴 뒤 검색 → `503 {"detail":"색인이 아직 없음 — ..."}`. 파일을 원위치한 뒤 재요청 → 다시 `200` 정상 — 장애·정상 복구 둘 다 확인.
- **회귀 확인**: 위 변경 이후 `python -m backend.indexing --validate-only` 재실행 → 그대로 통과(규칙 8·평가 10, 오류 0건) — ① 기능을 깨지 않음.

**실제 외부 호출 / mock 시험 / 미검증**
- 임베딩은 전부 로컬 모델(all-MiniLM-L6-v2) 실제 실행 — API 호출이 아니라 mock 도 아닌 실제 로컬 추론. 외부 네트워크 호출 없음(모델 가중치는 최초 1회 로컬 캐시에서 다운로드, `--check-embedding`과 무관).
- `main.py` 통짜 기동(`uvicorn backend.main:app`)은 이 환경에 `imageio_ffmpeg`(발음 평가용, RAG와 무관)이 없어 시도하지 못함 — RAG 라우터 자체는 `TestClient`로 실제 HTTP 계층까지 검증했으므로 이 미검증이 `/rag/search` 동작 자체의 공백은 아니다. 다만 "다른 팀원 라우터와 같은 프로세스에서 충돌 없이 뜨는지"는 실제로 통짜 기동을 해봐야 알 수 있어 **미검증으로 남김**(RAG 소유 범위 밖의 의존성 문제라 여기서 설치하지 않음).
- 저장소·평가 산출물 Git 제외: `data/chroma/`가 이미 `.gitignore`에 있음을 ①에서 확인함 — 새로 생성된 `manifest.json`·컬렉션 파일도 추적되지 않는 것을 `git status`로 재확인함(변경 없음으로 표시).

**종합 판정·다음 단계 전달**: 통과. 실제 데이터로 검색·재생성·재시작·오류 처리를 전부 실제 실행으로 확인했다. 다음(③ 검색 평가)로 넘어가려면 `golden.eval_set()` 기반 `tests/eval_rag.py`를 만들어 오류문장 8개 전체에 대해 hit@1/hit@3를 정식 기록하면 된다(이번 ②에서 손으로 돌려본 것은 2문장뿐이라 정식 평가는 아님). `main.py` 통짜 기동 문제(다른 담당자 의존성)는 팀장·TTS 담당에게 참고로만 전달.

### ③ 검색 평가 기록

- 기준 코드·확인 시각: 2026-09-09, ② 완료 상태(Chroma 기본 임베딩, `rules_20260909_000206684327` 등 최신 색인) 기준
- 변경 파일·평가 결과 경로: 신규 `tests/eval_rag.py`. `backend/rag.py`의 `/rag/eval`을 저장 결과 읽기로 구현(경로: `data/rag_eval/retrieval_eval_latest.json`, git 제외 확인됨). `backend/indexing.py`에 `RAG_EVAL_DIR`/`RETRIEVAL_EVAL_LATEST` 경로 상수 추가(두 파일이 같은 경로를 공유하도록).
- 데이터·색인 식별 정보: `data_hash=sha256:c2be97937abf7848`(①에서 확인한 값과 동일 — `_sample-B` 데이터 변경 없음), `active_collection` 은 평가 실행 시점의 최신 컬렉션, `model=all-MiniLM-L6-v2`, `k=3`, `threshold=null`

**분모·hit@1·hit@3·실패 수 (실제 실행, `python -m tests.eval_rag --retrieval-only`)**

```
대상 10문장 (오류 8 · 정상 2) · 검색 실패 0건
hit@1 = 0.5   hit@3 = 0.75   (목표 hit@3 ≥ 0.80)

[OK ] R-01  I play with my dog yesterday.        → 1위 R-01 (0.256)
[OK ] R-02  My sister like cats.                 → 1위 R-03 (0.338) *
[OK ] R-03  There are three bird in the tree.    → 1위 R-03 (0.236)
[OK ] R-04  I ate a orange.                      → 1위 R-04 (0.346)
[MISS] R-05  She is eat lunch now.                → 1위 R-08 (0.355)
[OK ] R-06  They is my friends.                  → 1위 R-06 (0.339)
[OK ] R-07  We are at the park yesterday.        → 1위 R-01 (0.297) *
[MISS] R-08  I have dog.                          → 1위 R-03 (0.366)
[--- ] NONE  I saw a big lion at the zoo.          → 1위 R-02 (0.381, 참고용)
[--- ] NONE  She likes bananas.                    → 1위 R-08 (0.449, 참고용)
```
(* = hit@3 안에는 들지만 1위는 아님 — hit@1 미스지만 hit@3 히트)

- **검색 실패 0건** — 색인 있음, 예외 없음. "실패를 분모에서 조용히 빼지 않는다"는 원칙은 이번엔 실패 자체가 없어 해당 없음.
- ②에서 손으로 확인했던 2문장(R-01, NONE 1개)과 점수·순위가 동일 — 회귀 없음.
- `/api/rag/eval` 조회 시험: `TestClient`로 `GET /api/rag/eval` 호출 → 저장된 값 그대로 반환(`n=8, total_n=10, normal_n=2, hit_at_1=0.5, hit_at_3=0.75`), 조회만으로 임베딩·검색이 재실행되지 않음(코드상 파일 읽기 + `load_manifest()`만 호출).
- **stale 표시 시험**: 저장된 결과의 `data_hash`를 임시로 다른 값으로 바꿔 `GET /api/rag/eval` 재호출 → `stale:true` 확인. 이후 실제 재평가를 다시 실행해 정상(`stale:false`) 상태로 복구 — 조작한 파일이 남지 않음.

**품질 목표 판정·미달 시 진행 결정**
- **품질 목표: 미달.** hit@3 75% (6/8) < 목표 80%. 결과를 조정하거나 표본을 바꿔 목표를 맞추지 않았다.
- 기능·계약 필수 조건은 전부 통과(위 시험 참고) — **미검증·실패 항목 없음.**
- work order의 판정 규칙대로: 기능·계약 통과 + 품질 미달 → **진행 결정은 "사용자 결정 대기"**로 기록한다. RAG 담당이 임의로 튜터 연결(④)에 적합하다고 판단하지 않는다.
- 참고: n=8이라 문장 1개(R-05 또는 R-08)만 더 맞아도 87.5%로 목표를 넘는다. 두 미스 모두 문장이 짧고 규칙 문구와 어휘 겹침이 적어서(R-05 "eat"만 있고 "-ing" 없음, R-08 "dog"가 규칙 예문에 없음) 생긴 것으로 보이며, 데이터 정식 납품(25개, 상황별 조각 3~5개로 확장)이 되면 개선될 가능성이 있다 — 그러나 이는 추정이며 재측정 전까지 확정 사실로 보고하지 않는다.

**종합 판정·다음 단계 전달**: 기능·계약 통과 / 품질 목표 미달 / 2026-09-09 최초 결정은 "여기서 멈추고 정식 데이터 대기"였음.

**결정 번복 (2026-09-09, 같은 날)**: 사용자가 `docs/0908/룰스초안.jsonl`(30개 초안) 검토를 거친 뒤 **"다시 8건(=`_sample-B`)으로 가서 ④ 진행"**을 명시적으로 지시함. 이는 hit@3 75%(목표 80% 미달) 상태를 사용자가 인지·수용하고 진행을 허용한 것으로, work order 규칙상 "**조건부 진행 가능**"으로 기록한다 — 목표 달성이나 필수 기능 검증 통과를 의미하지 않는다. `_sample-B` 8개는 여전히 개발용 샘플이며 독립적인 최종 성능이 아니다. 30개 초안은 아직 정식 데이터가 아니므로(검토 메모 `docs/0908/룰스초안-검토메모.md` 참고) 색인은 `_sample-B` 그대로 유지한다.

### ④ 연결 정보 인계·팀장 구현·통합 검증 기록

- **④-A 인계 상태**: 완료 (아래 전문). 계약 위치: 이 절 전체 + `backend/rag.py`(구현) + `backend/indexing.py`(색인/manifest)
- **④-B 팀장 구현 상태**: 미착수. `tutor.py`는 RAG 담당이 수정하지 않음 — 아래 인계 내용을 팀장이 반영해야 함
- **④-C 통합 검증 상태**: 미착수 (④-B 선행 필요)
- 팀장에게 전달할 수정 요청과 재검증 결과: 아래 "④-B 팀장 구현 요구사항" 참고. 재검증은 ④-B 완료 통보 후 진행

---

## ④-A 연결 정보 인계 (RAG 담당 → 팀장, 2026-09-09)

### 1. 실제 함수 계약 (예정이 아니라 지금 동작하는 코드)

```python
from backend.rag import search_rules
candidates = search_rules(text: str, k: int = 3) -> list[dict]
```

- **HTTP로 `/api/rag/search`를 다시 부르지 말고 이 함수를 직접 import 해서 쓸 것.** `/api/rag/search`는 이 함수를 감싼 API 래퍼일 뿐 별도 로직이 없음(같은 프로세스 내 호출이라 재호출은 불필요한 오버헤드).
- 반환: `score` 내림차순 정렬된 리스트. 각 항목 `{"id": "R-01", "type": "과거시제", "text": "...(원본 규칙 전체 본문)...", "unit": "U3", "score": 0.4367}`
  - `score = round(1 - cosine_distance, 4)`. **오류 확률이나 정확도가 아니라 유사도**(높을수록 관련 있음). 위·아래 경계값 없음(이론상 -1~1이지만 실측 분포는 3절 참고).
  - 저장 건수(현재 8개)를 넘는 `k`를 요청해도 초과 반환하지 않음 — `len(candidates)`가 `k`보다 작을 수 있음(예: `k=10`인데 저장 8개면 8개만 옴).
- **예외**: 색인이 없음·manifest가 가리키는 컬렉션을 열 수 없음·임베딩 실패·질의 실패 — 검색 과정에서 어디가 실패하든 전부 `backend.indexing.IndexUnavailableError`(→ `RuntimeError` 서브클래스) 하나로 정규화되어 던져짐(2026-09-09 코드 리뷰에서 임베딩·질의 실패가 정규화 안 되던 걸 발견해 수정 완료 — 수정 전엔 컬렉션 접근 실패만 이 예외로 잡혔음). `tutor.py`는 이 예외 하나만 캐치해서 `mode="fallback"`(전체 규칙)으로 전환하면 됨 — 현재 `/api/rag/search`는 이 예외를 503으로 매핑하지만, `tutor.py`는 HTTP를 안 타므로 직접 `except indexing.IndexUnavailableError` 로 잡아야 함.
- **호출 시간**: 외부 API 호출이 아니라 로컬 모델 추론(all-MiniLM-L6-v2, CPU). 규칙 8개 기준 실측 수십 ms 이내. 다만 프로세스 시작 후 첫 호출은 모델 로딩(초 단위)이 걸릴 수 있음 — 서버 기동 시 `search_rules("warmup")` 한 번 미리 불러 두는 걸 권장(선택 사항, 필수 아님).

### 2. `/api/rag/search` · `/api/rag/eval` 실제 요청·응답·오류 예시

```
GET /api/rag/search?q=I%20go%20to%20the%20zoo%20yesterday&k=3
200 {"query": "I go to the zoo yesterday", "chunks": [
  {"id":"R-01","type":"과거시제","text":"어제(yesterday), 지난주(last week)...","unit":"U3","score":0.4367},
  {"id":"R-02","type":"3인칭단수","text":"...","unit":"U3","score":0.2581},
  {"id":"R-04","type":"관사","text":"...","unit":"U3","score":0.2423}
], "threshold": null, "score_type": "cosine_similarity"}

GET /api/rag/search?q=%20   (공백만)
422 {"detail": "q 는 공백 제거 후 1~1000자여야 함"}

GET /api/rag/search?q=hello&k=999
422 {"detail": "k 는 1~10 사이여야 함"}

(색인 없음 상태에서)
GET /api/rag/search?q=hello
503 {"detail": "색인이 아직 없음 — 먼저 `python -m backend.indexing --rebuild` 실행 필요"}

GET /api/rag/eval
200 {"n":8,"total_n":10,"normal_n":2,"hit_at_1":0.5,"hit_at_3":0.75,"threshold":null,
     "search_failures":0,"k":3,"index":{...},"data_hash":"sha256:...","evaluated_at":"...",
     "stale":false,"runs":[{"label":"all-MiniLM-L6-v2","hit_at_1":0.5,"hit_at_3":0.75}],"rows":[...]}
```
`GET /rag/eval`은 `tests/eval_rag.py`가 저장한 파일만 읽는다 — 조회 자체는 검색·임베딩을 재실행하지 않음. `stale:true`면 지금 색인과 이 평가 결과의 데이터가 다르다는 뜻(재평가 필요 신호로 화면에 써도 됨).

### 3. ⚠ 중요 — 임계값(threshold)을 지금 켜면 위험한 이유 (실측 데이터)

`_sample-B` 8개로 실측한 검색 1위 점수:

| 구분 | 1위 점수 범위 | 평균 |
|---|---|---|
| 오류 문장(정답 맞힌 것) | 0.236 ~ 0.366 | 약 0.317 |
| **정상 문장(NONE, 오류 없음)** | **0.381 ~ 0.449** | **약 0.415** |

**정상 문장의 1위 점수가 오류 문장보다 오히려 더 높다.** "점수가 낮으면 정상 문장"이라는 직관적 가정이 지금 데이터·모델 조합에서는 반대로 나온다. 그래서:
- **`score < threshold` 만으로 "정상 문장(ok=true)"을 판정하지 마세요.** 표본이 작아 확정은 아니지만, 현재로선 신뢰할 수 없는 신호다.
- PRD-B 원안(`rule.score`가 임계값 미만이면 "걸리는 규칙 없음")을 그대로 구현하면 정상 문장을 오히려 더 강하게 오류로 몰아갈 위험이 있다.
- v0.2 work order 방침대로 **최초 기준선은 threshold 미설정을 유지**하고, "오류가 있는지"는 검색 점수가 아니라 **Gemini(LLM)의 판단(`ok` 필드)**에 맡길 것을 권장한다. 검색은 "1위 후보를 근거로 제공"하는 역할만 하고, 그 후보가 실제로 위반됐는지는 프롬프트·생성이 판단한다.
- threshold를 쓰고 싶다면 정식 데이터(25개) 확보 후 재실측해서 결정할 것을 권장.

### 4. `/fix` 필드 매핑 제안 (PRD-B 4.3 계약 기준, 현재 `tutor.py` 구조에 맞춤)

| 필드 | 채우는 방법 |
|---|---|
| `rule` | `candidates[0]` 있으면 `{"id":c["id"], "name":c["type"], "score":c["score"]}`, 없으면 `null` |
| `runner_up` | `candidates[1]` 있으면 같은 형식, 없으면 `null` (현재 `_sample-B`는 8개라 `k=3`이면 거의 항상 2위가 있음) |
| `source` | `{"chunk_id": candidates[0]["id"], "text": candidates[0]["text"]}` — **모델이 만든 출처를 쓰지 말고 서버가 전달한 후보에서 그대로 구성**(work order가 반복 강조하는 부분) |
| `mode` | 검색 성공(`IndexUnavailableError` 없이 `candidates` 반환) → `"rag"`. 예외 발생 → `"fallback"` |
| `fallback_reason` | `mode="fallback"`일 때만: 색인 없음이면 `"search_error"`, (threshold 도입 시) 관련성 낮음이면 `"low_relevance"` — 현재는 threshold 미설정이라 `"search_error"`만 발생 가능 |
| 프롬프트에 넣을 근거 | 최초 기준선: `candidates[0]`(1위) 하나만 `_rules_block()`에 전달. `fallback`이면 기존처럼 `golden.rules()` 전체 |

### 5. 정상 검색·장애·근거 밖 ID 시험 사례 (팀장이 `tutor.py`에서 재현·검증할 것)

| 사례 | 입력 | 기대 동작 |
|---|---|---|
| 정상 검색 | `"I go to the zoo yesterday"` | `search_rules()` → `[{"id":"R-01",...,"score":0.4367}, ...]`, `mode="rag"` |
| 색인 없음(장애) | (임시로 `data/chroma/manifest.json` 제거 후 호출) | `IndexUnavailableError` 발생 → `tutor.py`는 이걸 잡아 전체 규칙 폴백, `mode="fallback"`, `fallback_reason="search_error"` |
| 근거 밖 ID | Gemini가 `candidates`에 없는 `rule_id`를 응답에 넣은 경우 | **현재 코드 버그**: `tutor.py`가 `golden.find_rule()`로 전체 목록에서만 존재 확인 후 `ok=true`로 바꿔버림(근거 밖이어도 "정상"으로 처리됨). RAG 연결 후엔 "실제 전달한 `candidates`에 있는 ID인지"까지 검증하도록 바꿔야 함 — 없으면 `ok=true`가 아니라 502로 처리 (v0.2 work order 5절·7절 요구사항과 동일) |
| k보다 후보가 적을 때 | (해당 없음, 현재 8개 규칙 + k=3이면 항상 3개 옴) | 저장 건수가 3 미만으로 줄어들면 `len(candidates) < k`일 수 있음 — `runner_up` 계산 시 `candidates[1]` 존재 여부 확인 필요 |

### 6. 화면 버그 — 근거 배지 문구가 실제 mode와 안 맞음 (2026-09-09 프론트엔드 실동작 점검으로 확인)

`frontend/js/tutor.js`의 진단 카드가 `mode`와 무관하게 항상 `📚 <b>RAG가 찾은 근거</b> · {chunk_id}`로 표시한다:
```js
d.innerHTML = `...<div class="src">📚 <b>RAG가 찾은 근거</b> · ${esc(r.source?.chunk_id || '')}...`
```
그 아래 mode별 작은 안내 배지(`서버 /fix · 규칙 전체를 Gemini에 넣는 폴백 모드 (RAG 검색 연결 전)` 등)가 따로 붙지만, 바로 위 큰 라벨은 `mode="fallback"`·`mode="local"`에서도 "RAG가 찾은 근거"라고 말해버려 서로 모순된 문구가 동시에 뜬다. 실제로 앱을 띄워 `mode="fallback"` 상태에서 확인한 화면 텍스트:
```
📚 RAG가 찾은 근거 · R-01
어제(yesterday)... (규칙 본문)
서버 /fix · 규칙 전체를 Gemini에 넣는 폴백 모드 (RAG 검색 연결 전)
```
v0.2 work order §9("전체 규칙 근거도 RAG가 찾은 근거라는 문구로 표시")가 이미 지적했던 항목인데, 이번에 실제 화면 문구로 재확인했다. `mode="rag"`일 때만 "RAG가 찾은 근거"라 하고 `mode="fallback"`일 때는 다른 표현(예: "전체 규칙 중 하나")으로 바꿔줄 것을 인계.

### 7. 기록 없는 내부 교정 함수 (④-C 통합 검증용 — 팀장이 준비해줄 것)

④-C에서 RAG 담당과 공동으로 "정상 문장 오교정" 등을 평가하려면, `sentence_log.jsonl`·`notebook.json`에 기록을 남기지 않는 내부 함수가 필요하다(공개 API에 기록 해제 옵션을 노출하지 않는다는 원칙 유지). 제안 시그니처:

```python
# backend/tutor.py 에 추가 제안 — 팀장 구현
def fix_internal(text: str, level: int = 2, unit: str = "") -> dict:
    """POST /fix 와 같은 로직이되 _log_sentence()/_notebook_add() 를 호출하지 않는다.
    반환 형식은 POST /fix 응답과 동일. tests/eval_rag.py --with-generation 이 이 함수를 쓴다."""
```
RAG 담당은 이 함수가 준비되면 `tests/eval_rag.py`에 `--with-generation` 옵션을 추가해 이 함수를 호출하도록 확장할 수 있다(이번 ④-A에서는 아직 구현하지 않음 — 함수가 없어서 만들 수 없음).

---

## ④-B 팀장 구현 요구사항 (v0.2 work order §7 그대로 인용, 참고용)

- `_search_rule()`의 스텁을 위 `search_rules()` 호출로 교체하고 후보 목록·점수·차순위를 보존한다.
- 상위 3개를 검색하되 최초 기준선은 1위 규칙만 생성 근거로 전달한다.
- 검색 장애(`IndexUnavailableError`) 시 전체 규칙으로 전환한다. **3절의 이유로 "낮은 점수 = 정상 문장"으로 단정하지 않는다.**
- `rule.score`, `runner_up`을 실제 검색 결과로 구성. 전체 규칙 모드는 점수·차순위 `null` 유지.
- 근거 밖 ID(위 5절)를 `ok=true`로 바꾸는 현재 처리를 제거하고 502로 명시적 오류 처리.
- `fallback_reason` 필드 추가.

## ④-C 완료 기준 (참고용, ④-B 완료 후 재개)

실제 검색을 사용한 `/fix` 응답의 모드·근거·점수가 일치, 잘못된 출력·장애가 정상 판정으로 바뀌지 않음, 기존 응답 호환·학생 기록 검증 통과. 정상 문장 오교정·생성 실패는 `fix_internal()`로 기록 없이 평가.

---

- 기준 코드·확인 시각: 2026-09-09, ③ 완료 상태(`_sample-B` 색인, hit@3 75%) 기준
- 변경 파일·유지한 응답 계약: 이번엔 코드 변경 없음(인계 문서만 작성). 기존 `/fix` 응답 계약(`ok/rule/runner_up/wrong/fix/fixed/why/source/more_errors/full_fixed/suggested_questions/mission/log_id/mode`) 유지 전제로 매핑 제안함
- 완료 조건별 증거와 실행 명령: 위 1~6절이 ④-A 체크리스트(import 경로·후보 계약·임계값 처리·API 예시·필드 매핑·시험 사례·기록없는 함수 제안) 전항목 충족
- 정상 문장 평가·생성 실패·복수 오류 제한: ④-C 대상 — 아직 미착수(④-B 선행 필요)
- 학생 기록 보호 확인: ④-C 대상 — 아직 미착수
- 다른 담당자 인계 사항: 위 전체가 팀장 인계 사항. 추가로 3절(threshold 위험성)·6절(근거 배지 문구 오표시, 실제 화면으로 확인함)은 특히 눈에 띄게 전달할 것
- **종합 판정: ④-A 완료 · ④-B 팀장 구현 대기.** ④ 전체는 완료가 아님 — RAG 담당이 tutor.py를 대신 구현하거나 이 상태를 ④ 전체 완료로 보고하지 않는다.

### 최종 판정

- 전체 상태: 미착수
- 실행하지 않은 검증:
- 남은 필수 조치:
- 완료 증거와 실행 방법:

work order의 체크 상태와 충돌하지 않도록 구현자가 단계 종료 시 상태를 함께 맞춘다. 상세 실행 증거는 이 진행 문서에 기록하고 work order에는 단계 상태와 이 문서 참조만 남겨 중복 관리하지 않는다.
