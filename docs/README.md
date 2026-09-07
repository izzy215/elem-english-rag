# docs — 기획 문서 안내

두 방향을 나란히 두고 검토 중 (2026-09-07). **결정 전까지 둘 다 유지.**

| 폴더 | 방향 | 한 줄 |
|---|---|---|
| [plan-A/](plan-A/) | 단어 학습 + 4지선다 + 오답 단어 복습 | 단어 틀림 → 그 단어 설명 (id 조회 위주, RAG는 보조) |
| [plan-B/](plan-B/) | **내 문장 고쳐주기 튜터** | 학생이 말하거나 쓴 문장 → RAG가 문법 규칙 검색 → 고쳐주기 → 오답노트(문법) |
| [common/](common/) | 공통 | 아키텍처 흐름도(콘텐츠/형식/서버/화면 분리), 데이터 파이프라인 원본 그림 |

## 각 폴더 구성

| 문서 | plan-A | plan-B |
|---|---|---|
| 간단기획서 | 간단기획서.md / .html | 간단기획서.md |
| PRD (화면 · API · 데이터) | PRD.md / .html | PRD.md |
| 클릭형 목업 | mockup.html | mockup.html (따라 말하기 · 튜터 · 오답노트 · 규칙 연습 · 관리자) |
| 데이터 제작 계획 | data-pipeline-plan.md / .svg | data-pipeline-plan.md (규칙 조각 중심) |
| 설계서 | design-screens · design-quiz · design-backlog | (B 확정 후 작성) |
| 다이어그램 | overview.svg | diagrams.md (유스케이스 · 시퀀스 4 · Mermaid) |

## 보는 순서

1. `common/architecture-flow.svg` — 무엇이 바뀌고 무엇이 고정인지
2. 두 목업을 나란히: `plan-A/mockup.html` vs `plan-B/mockup.html` (더블클릭, 오른쪽 위 "기획 메모 보기")
3. 고른 쪽의 간단기획서 → PRD → 데이터 계획

## 결정되면

- 선택된 폴더의 문서에 html · 공유 링크 생성, 설계서 작성
- 선택 안 된 폴더는 `archive/` 로 이동 (삭제하지 않음)
- A와 B의 차이는 [plan-B/간단기획서.md](plan-B/간단기획서.md) 2절 "왜 B인가" 참고
