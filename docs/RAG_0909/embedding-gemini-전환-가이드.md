# embedding.py를 Gemini로 바꾸는 방법 (참고용 — 미적용)

작성일: 2026-09-09 · 상태: **참고만, 실제로 적용 안 함** (현재 채택은 Chroma 기본 로컬 임베딩 all-MiniLM-L6-v2)

## 바뀐 코드 (예시)

```python
"""
임베딩 — Gemini 버전 (gemini-embedding-001, 3072차원)
GEMINI_API_KEY 필요. 문서/질의를 task_type으로 구분해서 호출한다.
"""
from __future__ import annotations

from backend.config import settings

EMBEDDING_PROVIDER = "google-genai"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    resp = _get_client().models.embed_content(
        model=EMBEDDING_MODEL, contents=texts, config={"task_type": task_type},
    )
    return [list(e.values) for e in resp.embeddings]


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _embed([text], "RETRIEVAL_QUERY")[0]
```

## 달라지는 점

| 항목 | 로컬(현재 채택) | Gemini로 바꾸면 |
|---|---|---|
| import | `chromadb.utils.embedding_functions` | `google.genai` + `backend.config.settings` |
| 문서/질의 구분 | 없음(같은 함수) | `task_type`으로 구분(`RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`) — **함수 시그니처는 그대로라 호출부(`rag.py`, `indexing.py`)는 안 고쳐도 됨** |
| `EMBEDDING_DIM` | 384 | 3072 |
| 외부 호출 | 없음(로컬) | 있음(API 호출, 네트워크 필요) |
| 비용/키 | 무료, 키 불필요 | `GEMINI_API_KEY` 필요, 호출당 과금 |
| `gemini-embedding-2-preview` 주의 | — | 배치 호출이 깨져서(8개 넣으면 1개만 옴, 실행 단위 ①에서 실측 확인) `gemini-embedding-001`만 써야 함 |

## 이것만 바꾸면 끝나는 이유

`embed_documents(texts) -> list[list[float]]`, `embed_query(text) -> list[float]` **시그니처가 동일**하게 설계돼 있어서 `indexing.py`(색인)와 `rag.py`(검색)는 `from backend import embedding`으로 이 함수만 부르지 어떤 모델인지 모릅니다. 딱 한 가지 추가로 해야 할 일:

- **차원이 384→3072로 바뀌므로 기존 Chroma 색인은 재사용 불가.** `python -m backend.indexing --rebuild`를 다시 돌려야 새 컬렉션이 3072차원으로 만들어집니다(코드 수정 없이 명령만 다시 실행하면 됨 — `build_index()`가 매번 새 컬렉션을 만드는 구조라 자동으로 해결됨).

## 왜 지금은 안 바꿨는지

실행 단위 ①에서 `_sample-B`(8개) 기준으로 로컬 모델과 Gemini `gemini-embedding-001`을 실측 비교한 결과 hit@3 75%로 동률이었고, 성능 차이가 없어 API 키·과금이 필요 없는 로컬 모델을 사용자가 최종 채택했습니다. 정식 데이터(25개) 확보 후 재측정에서 Gemini가 뚜렷이 나으면 이 문서대로 전환을 재검토할 수 있습니다.
