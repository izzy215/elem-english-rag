# embedding.py와 Chroma의 관계 — 패키지 vs DB

작성일: 2026-09-09

## 결론

`backend/embedding.py`가 필요로 하는 건 **"Chroma DB(색인 파일)"가 아니라 `chromadb` 패키지**입니다. 미묘하지만 다른 얘기라 정리합니다.

## 코드로 확인

```python
# backend/embedding.py
def _get_ef():
    global _ef
    if _ef is None:
        from chromadb.utils import embedding_functions   # ← 여기서 chromadb 패키지를 씀
        _ef = embedding_functions.DefaultEmbeddingFunction()
    return _ef

def embed_documents(texts: list[str]) -> list[list[float]]:
    vectors = _get_ef()(texts)   # 그냥 텍스트 → 벡터 계산만 함
    ...
```

- 우리가 고른 임베딩 모델(all-MiniLM-L6-v2)이 **chromadb 패키지 안에 내장 유틸리티로 딸려오는 것**이라(`chromadb.utils.embedding_functions.DefaultEmbeddingFunction`), 그걸 가져다 쓰려면 `chromadb`가 설치돼 있어야 합니다.
- 하지만 `embed_documents()`/`embed_query()`는 **Chroma DB(`data/chroma/` 폴더, `manifest.json`, 컬렉션)와는 아무 상관 없습니다.** DB 연결·파일 읽기를 전혀 안 하고, 그냥 "텍스트 넣으면 벡터 숫자 나오는" 순수 계산 함수입니다.

## 정리

| 파일 | 필요한 것 |
|---|---|
| `embedding.py` | `chromadb` **패키지**(pip install) — DB 파일은 필요 없음, 텍스트→벡터 변환기만 빌려 씀 |
| `indexing.py` | `chromadb` 패키지 + 실제 Chroma **DB**(`PersistentClient`로 `data/chroma/` 읽고 씀) |
| `rag.py` | 위와 동일 — 검색할 때 Chroma DB 조회 |

## 참고

나중에 임베딩 모델을 Gemini 같은 걸로 바꾸면, `embedding.py`는 `chromadb` 없이도 동작하게 됩니다(그냥 Gemini API만 호출). 지금은 우연히 "임베딩 모델 제공자"와 "벡터 저장소"가 둘 다 chromadb라는 같은 패키지라서 헷갈리기 쉬운데, 원래는 서로 독립적인 역할입니다. (관련: [embedding-gemini-전환-가이드.md](embedding-gemini-전환-가이드.md))

---

## 임베딩 모델 실측 비교 (실행 단위 ①, `_sample-B` 8개 기준)

### 실제 계정 호출 가능 여부 (`python -m backend.indexing --check-embedding`)

| 모델 | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | 차원 | 비고 |
|---|---|---|---|---|
| `text-embedding-004` | 실패 (404) | 실패 (404) | — | 이 계정/API 버전에서 `embedContent` 미지원 — SDK 예시에 있다고 실제로 되는 게 아님을 확인 |
| `gemini-embedding-001` | 성공 | 성공 | 3072 | 8개 배치 입력 정상 반환 확인 |
| `gemini-embedding-2-preview` | 성공(단건) | — | 3072 | **8개를 한 번에 넣으면 응답 embeddings가 1개만 옴**(배치 미지원 또는 다른 동작) — `embed_documents(texts: list[str])` 배치 계약에 안 맞아 후보에서 제외 |

### 실측 검색 성능 비교 (규칙 8개 색인, 오류문장 8개로 hit@1·hit@3, n=8이라 1건=12.5%p)

| 임베딩 | 키 필요 | 비용 | hit@1 | hit@3 | 놓친 문장 |
|---|---|---|---|---|---|
| Chroma 기본(all-MiniLM-L6-v2, 영어전용, 로컬) | ✕ | 무료 | 50% (4/8) | 75% (6/8) | R-05(현재진행형), R-08(관사a) |
| 다국어 로컬(paraphrase-multilingual-MiniLM-L12-v2) | ✕ | 무료 | 50% (4/8) | 75% (6/8) | R-05, R-08 (로컬 기본과 동일) |
| **Gemini `gemini-embedding-001`** | ○ | API 과금 | 50% (4/8) | 75% (6/8) | R-04(관사an), R-08(관사a) — 놓친 문장 자체는 로컬과 다름 |

세 후보 모두 이 8문항 샘플에서는 **동일하게 hit@3 75%로 목표(80%) 미달**. 표본이 너무 작아(n=8) 어느 쪽이 "더 낫다"고 단정할 근거는 아니며, 데이터 정식 납품(25개) 후 재측정이 필요합니다. 성능이 동률이라 API 키·과금이 필요 없는 Chroma 기본 로컬 모델을 최종 채택했습니다.
