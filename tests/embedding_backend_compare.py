"""
임베딩 백엔드 비교용 임시 테스트 스크립트 (테스트 목적 — backend/embedding.py는 건드리지 않음)

backend/embedding.py 는 RAG 담당 파일이라 직접 수정하지 않고, 이 스크립트가 실행 중에만
backend.embedding 모듈의 embed_documents/embed_query 를 바꿔치기(monkeypatch)해서 팀원 누구나
자기 컴퓨터에서 원하는 백엔드로 색인·평가해볼 수 있게 했다. 프로세스가 끝나면 흔적 없이 사라진다
— embedding.py 파일 자체는 한 글자도 안 바뀜.

사용:
    python -m tests.embedding_backend_compare --backend gemini
    python -m tests.embedding_backend_compare --backend local --model intfloat/multilingual-e5-base
        (pip install sentence-transformers 필요)
    python -m tests.embedding_backend_compare --backend remote --url http://192.168.1.147:8002
        (강의실 서버에 backend/embed_server.py 를 먼저 띄워둬야 함)

주의: 실행하면 data/chroma/ 의 실제 색인을 그 백엔드로 다시 만든다 — data/chroma/ 는 팀원과
공유되는 게 아니라 각자 로컬 파일이라 안전함(.gitignore). 다 써보고 원래 쓰던 백엔드로
되돌리려면 embedding.py 를 원상태로 둔 채 `python -m backend.indexing --rebuild` 를
다시 실행하면 됨.

hit@1/hit@3 채점 기준은 tests/eval_rag.py 와 완전히 동일(golden.eval_set() + search_rules()).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":   # eval_rag.py 등이 찍는 유니코드 기호(—, ≥)가 cp949 콘솔에서 안 깨지게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import embedding, indexing              # noqa: E402
from tests.eval_rag import run_retrieval_eval, _print_summary  # noqa: E402

# 2026-09-10 로컬 실측(hit@1, n=65, 참고용) — all-MiniLM-L6-v2 0.7077 · multilingual-e5-base
# 0.7231(로컬 후보 중 최고) · multilingual-e5-large 0.6923 · all-mpnet-base-v2 0.6154 ·
# BAAI/bge-m3 0.6000 · paraphrase-multilingual-mpnet-base-v2 0.5538 · Gemini 0.7692(현재 채택)
_KNOWN_DIMS = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "paraphrase-multilingual-mpnet-base-v2": 768,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,
    "BAAI/bge-m3": 1024,
}


def _patch_gemini() -> None:
    import math
    from backend.config import settings

    embedding.EMBEDDING_PROVIDER = "google-genai"
    embedding.EMBEDDING_MODEL = "gemini-embedding-001"
    embedding.EMBEDDING_DIM = 3072

    client_box = {"c": None}

    def _get_client():
        if client_box["c"] is None:
            from google import genai
            client_box["c"] = genai.Client(api_key=settings.gemini_api_key)
        return client_box["c"]

    def _embed(texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        resp = _get_client().models.embed_content(
            model=embedding.EMBEDDING_MODEL, contents=texts, config={"task_type": task_type})
        vectors = [list(item.values) for item in (resp.embeddings or [])]
        if len(vectors) != len(texts):
            raise ValueError("Gemini embedding response count mismatch")
        if any(len(v) != embedding.EMBEDDING_DIM or not all(math.isfinite(x) for x in v) or not any(v) for v in vectors):
            raise ValueError("Gemini embedding response has invalid dimension or values")
        return vectors

    embedding.embed_documents = lambda texts: _embed(texts, "RETRIEVAL_DOCUMENT")
    embedding.embed_query = lambda text: _embed([text], "RETRIEVAL_QUERY")[0]


def _patch_local(model_name: str) -> None:
    from sentence_transformers import SentenceTransformer

    embedding.EMBEDDING_PROVIDER = "sentence-transformers-local"
    embedding.EMBEDDING_MODEL = model_name
    embedding.EMBEDDING_DIM = _KNOWN_DIMS.get(model_name, 0)

    st = SentenceTransformer(model_name)
    get_dim = getattr(st, "get_embedding_dimension", st.get_sentence_embedding_dimension)
    embedding.EMBEDDING_DIM = get_dim()
    needs_prefix = "e5-" in model_name

    def _embed(texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        if needs_prefix:
            p = "passage: " if task_type == "RETRIEVAL_DOCUMENT" else "query: "
            texts = [p + t for t in texts]
        vectors = st.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [[float(x) for x in v] for v in vectors]

    embedding.embed_documents = lambda texts: _embed(texts, "RETRIEVAL_DOCUMENT")
    embedding.embed_query = lambda text: _embed([text], "RETRIEVAL_QUERY")[0]


def _patch_remote(url: str, model_name: str) -> None:
    import requests

    embedding.EMBEDDING_PROVIDER = "remote-http"
    embedding.EMBEDDING_MODEL = model_name
    embedding.EMBEDDING_DIM = _KNOWN_DIMS.get(model_name, 0)

    def _embed(texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        resp = requests.post(url.rstrip("/") + "/embed", json={"texts": texts, "task_type": task_type}, timeout=30)
        resp.raise_for_status()
        vectors = resp.json()["embeddings"]
        if vectors:
            embedding.EMBEDDING_DIM = len(vectors[0])
        return vectors

    embedding.embed_documents = lambda texts: _embed(texts, "RETRIEVAL_DOCUMENT")
    embedding.embed_query = lambda text: _embed([text], "RETRIEVAL_QUERY")[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gemini", "local", "remote"], required=True)
    parser.add_argument("--model", default="intfloat/multilingual-e5-base", help="local/remote 백엔드의 모델 이름")
    parser.add_argument("--url", default="http://192.168.1.147:8002", help="remote 백엔드(embed_server.py) 주소")
    args = parser.parse_args()

    if args.backend == "gemini":
        _patch_gemini()
    elif args.backend == "local":
        _patch_local(args.model)
    else:
        _patch_remote(args.url, args.model)

    print(f"[compare] 색인 재생성 중 - provider={embedding.EMBEDDING_PROVIDER} model={embedding.EMBEDDING_MODEL}")
    manifest = indexing.build_index()
    print(f"[compare] 색인 완료: {manifest['count']}건, dim={manifest['dim']}")

    result = run_retrieval_eval()
    _print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
