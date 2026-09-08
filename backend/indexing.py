"""
RAG 색인 준비   담당: RAG 담당

사용:
    python -m backend.indexing --validate-only     외부 호출 없이 데이터만 검증 (실행 단위 ①)
    python -m backend.indexing --rebuild            실제 임베딩 + Chroma 색인 생성/교체 (실행 단위 ②)
    python -m backend.indexing --check-embedding    Gemini 임베딩 후보를 실제 계정으로 시험 호출 (참고용 비교, 현재 채택 안 함)

색인은 data/chroma/ 에 영속 저장한다(.gitignore 됨). 컬렉션 이름은 `rules_<타임스탬프>` 로 매번 새로
만들고, 임베딩·저장 건수가 원본과 일치함을 확인한 뒤에만 data/chroma/manifest.json 을 새 컬렉션으로
원자적 교체한다(임시 파일에 쓰고 os.replace). 그래서 --rebuild 도중 실패해도 이전 manifest.json 이
가리키는 색인은 그대로 남아 서비스가 깨지지 않는다. 교체가 끝난 뒤에만 이전 rules_* 컬렉션을 지운다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend import golden

REQUIRED_RULE_FIELDS = ("id", "type", "unit", "text")

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "data" / "chroma"
MANIFEST_PATH = CHROMA_DIR / "manifest.json"
COLLECTION_PREFIX = "rules_"
TEXT_VERSION = "rule.text_raw_v1"   # rules.jsonl 의 text 필드를 그대로 검색 본문으로 씀 (examples 재첨부 없음)

RAG_EVAL_DIR = ROOT / "data" / "rag_eval"                              # 실행 단위 ③(tests/eval_rag.py)이 씀
RETRIEVAL_EVAL_LATEST = RAG_EVAL_DIR / "retrieval_eval_latest.json"     # GET /api/rag/eval 이 읽는 파일


class IndexUnavailableError(RuntimeError):
    """색인이 아직 없거나(첫 --rebuild 전) manifest 가 가리키는 컬렉션을 열 수 없을 때."""


@dataclass
class ValidationReport:
    data_dir: str
    using_sample: bool
    rule_count: int = 0
    eval_total: int = 0
    eval_error_n: int = 0
    eval_normal_n: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate() -> ValidationReport:
    data_dir = golden._dir()  # noqa: SLF001 — 검증 스크립트라 내부 선택 경로를 그대로 노출해 보고한다
    report = ValidationReport(data_dir=str(data_dir), using_sample=golden.using_sample())

    try:
        rules = golden.rules()
    except (ValueError, OSError) as exc:
        report.errors.append(f"rules.jsonl — 읽기/파싱 실패(잘못된 JSON 가능성): {exc}")
        return report
    report.rule_count = len(rules)

    # ── rules.jsonl: 필수 필드 · 중복 ID · 빈 본문 (파일명·행 번호로 보고) ──
    seen_ids: dict[str, int] = {}
    for i, r in enumerate(rules, start=1):  # golden._read_jsonl 은 빈 줄을 이미 제외하고 읽으므로 순서가 곧 원본 행 번호
        for field_name in REQUIRED_RULE_FIELDS:
            v = r.get(field_name)
            if not isinstance(v, str) or not v.strip():
                report.errors.append(f"rules.jsonl:{i} — 필수 필드 '{field_name}' 없음/빈 문자열 (id={r.get('id')!r})")
        rid = r.get("id")
        if rid:
            if rid in seen_ids:
                report.errors.append(f"rules.jsonl:{i} — 중복 id {rid!r} (처음 등장: 행 {seen_ids[rid]})")
            else:
                seen_ids[rid] = i

    valid_rule_ids = set(seen_ids)

    # ── eval.csv: 정답 ID 참조 · NONE 예외 · 시험지-교재 중복 ──
    eval_rows = golden.eval_set()
    report.eval_total = len(eval_rows)
    wrong_examples = {r.get("wrong_example", "").strip() for r in rules if r.get("wrong_example")}
    try:
        error_rows = golden.errors()
    except (ValueError, OSError) as exc:
        report.errors.append(f"errors.jsonl — 읽기/파싱 실패(잘못된 JSON 가능성): {exc}")
        error_rows = []
    error_texts = {e.get("error", "").strip() for e in error_rows if e.get("error")}

    for i, row in enumerate(eval_rows, start=1):
        text = (row.get("text") or "").strip()
        expected = (row.get("expected_rule_id") or "").strip()
        if not text:
            report.errors.append(f"eval.csv:{i} — text 비어 있음")
            continue
        if expected == "NONE":
            report.eval_normal_n += 1
        elif not expected:
            report.errors.append(f"eval.csv:{i} — expected_rule_id 비어 있음 (NONE도 아님)")
        elif expected not in valid_rule_ids:
            report.errors.append(f"eval.csv:{i} — expected_rule_id {expected!r} 가 rules.jsonl 에 없음")
            report.eval_error_n += 1
        else:
            report.eval_error_n += 1
        if text in wrong_examples:
            report.warnings.append(f"eval.csv:{i} — text 가 rules.jsonl 의 wrong_example 과 동일: {text!r}")
        if text in error_texts:
            report.warnings.append(f"eval.csv:{i} — text 가 errors.jsonl 의 error 와 동일: {text!r}")

    # ── unit 참조 정합성 (참고용 경고 — ALL 스코프 규칙은 대상에서 제외) ──
    units_rule_ids: set[str] = set()
    for u in golden._read("units.csv"):  # noqa: SLF001 — golden.py 에 unit별 rule_ids 조회 함수가 없어 원본 로더를 그대로 재사용
        units_rule_ids.update(x for x in (u.get("rule_ids") or "").split(";") if x)
    unreferenced = sorted(valid_rule_ids - units_rule_ids - {r["id"] for r in rules if r.get("unit") == "ALL"})
    if unreferenced:
        report.warnings.append(f"어느 unit의 rule_ids 에도 없는 규칙(ALL 제외): {unreferenced}")

    return report


def _print_report(report: ValidationReport) -> None:
    print(f"[indexing] 데이터 폴더: {report.data_dir} (샘플 사용: {report.using_sample})")
    print(f"[indexing] 규칙 {report.rule_count}개 · 평가 {report.eval_total}개 (오류 {report.eval_error_n} · 정상 {report.eval_normal_n})")
    for w in report.warnings:
        print(f"[indexing][경고] {w}")
    for e in report.errors:
        print(f"[indexing][오류] {e}")
    print(f"[indexing] 결과: {'통과' if report.ok else '실패'}")


# ─────────────────────────────────────────────
# 실행 단위 ② — 임베딩·색인
# ─────────────────────────────────────────────
def _chroma_client():
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _data_hash(rules: list[dict]) -> str:
    """rules.jsonl 내용이 바뀌면 값이 바뀌는 지문. id 순으로 정렬해 파일 안 순서와 무관하게 만든다."""
    payload = json.dumps(
        [{"id": r["id"], "text": r["text"]} for r in sorted(rules, key=lambda r: r["id"])],
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise IndexUnavailableError("색인이 아직 없음 — 먼저 `python -m backend.indexing --rebuild` 실행 필요")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def build_index() -> dict:
    """검증 통과 → 임베딩 → 임시 컬렉션 생성·검증 → manifest 원자적 교체 → 이전 컬렉션 정리."""
    report = validate()
    if not report.ok:
        raise RuntimeError("데이터 검증 실패 — 색인을 만들지 않음: " + "; ".join(report.errors))

    rules = golden.rules()
    from backend import embedding
    vectors = embedding.embed_documents([r["text"] for r in rules])
    if len(vectors) != len(rules):
        raise RuntimeError(f"임베딩 결과 수({len(vectors)})가 규칙 수({len(rules)})와 다름 — 활성 색인 전환하지 않음")
    dim = len(vectors[0]) if vectors else 0

    client = _chroma_client()
    name = f"{COLLECTION_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    try:
        col.add(
            ids=[r["id"] for r in rules],
            embeddings=vectors,
            documents=[r["text"] for r in rules],
            metadatas=[
                {"type": r["type"], "unit": r.get("unit", ""), "source_file": "rules.jsonl", "source_line": i}
                for i, r in enumerate(rules, start=1)
            ],
        )
        actual = col.count()
    except Exception:
        client.delete_collection(name)   # 저장 도중 실패한 컬렉션을 고아로 남기지 않음
        raise
    if actual != len(rules):
        client.delete_collection(name)   # 절반만 들어간 컬렉션을 남기지 않음
        raise RuntimeError(f"색인 건수 불일치: 저장 {actual} vs 원본 {len(rules)} — 활성 색인 전환하지 않음")

    manifest = {
        "active_collection": name,
        "provider": embedding.EMBEDDING_PROVIDER,
        "model": embedding.EMBEDDING_MODEL,
        "dim": dim,
        "distance": "cosine",
        "text_version": TEXT_VERSION,
        "count": actual,
        "data_hash": _data_hash(rules),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    tmp_path = MANIFEST_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(MANIFEST_PATH)   # 원자적 교체. 여기서 죽어도 이전 manifest.json 은 그대로 유효

    for c in client.list_collections():   # 정리는 교체가 끝난 뒤에만 — 실패 시 이전 색인을 건드리지 않기 위함
        if c.name.startswith(COLLECTION_PREFIX) and c.name != name:
            client.delete_collection(c.name)

    return manifest


# 후보 순서: SDK(google-genai 2.x) embed_content 예시가 쓰는 이름을 먼저, 그 다음 최신 세대 이름 순.
# 계정마다 사용 가능한 모델이 다를 수 있어 하나만 가정하지 않고 전부 시도해 실제로 되는 것만 채택한다.
EMBEDDING_MODEL_CANDIDATES = ["text-embedding-004", "gemini-embedding-001", "gemini-embedding-2-preview"]


def check_embedding() -> int:
    """실제 계정으로 embed_content 호출 1회 — 이 함수만 외부 호출을 한다(--validate-only 와 분리).
    GEMINI_API_KEY 가 있어야 의미 있는 결과가 나온다. 문서/질의 두 task_type 을 각각 시도해
    같은 모델이 둘 다 받아주는지도 함께 확인한다."""
    from backend.config import settings
    if not settings.has_api_key:
        print("[indexing] GEMINI_API_KEY 가 없어 임베딩 실제 호출을 확인할 수 없음 (.env 에 키를 넣고 다시 실행)")
        return 2

    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)

    any_ok = False
    for model in EMBEDDING_MODEL_CANDIDATES:
        for task_type, sample in (("RETRIEVAL_DOCUMENT", "테스트 문서 조각"), ("RETRIEVAL_QUERY", "테스트 질의")):
            try:
                resp = client.models.embed_content(model=model, contents=[sample], config={"task_type": task_type})
                dim = len(resp.embeddings[0].values) if resp.embeddings and resp.embeddings[0].values else 0
                print(f"[indexing] 성공 · model={model} task_type={task_type} → 차원 {dim}")
                any_ok = True
            except Exception as e:  # noqa: BLE001 — 계정별로 어떤 예외 타입이 오는지 모르므로 전부 잡아 그대로 보고
                print(f"[indexing] 실패 · model={model} task_type={task_type} → {type(e).__name__}: {e}")
    if not any_ok:
        print("[indexing] 시도한 후보 전부 실패 — 실제 계정에서 지원하는 임베딩 모델명을 다시 확인해야 함")
        return 1
    print("[indexing] 위에서 '성공'으로 표시된 model 을 EMBEDDING_MODEL 로 확정한다 (task_type 은 문서/질의 각각 유지)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true", help="외부 호출 없이 데이터만 검증")
    parser.add_argument("--rebuild", action="store_true", help="임베딩(로컬 모델) + Chroma 색인 생성/교체")
    parser.add_argument("--check-embedding", action="store_true", help="Gemini 임베딩 후보를 실제 계정으로 시험 호출 (참고 비교용, 현재 채택 안 함)")
    args = parser.parse_args(argv)

    if args.check_embedding:
        return check_embedding()

    if args.rebuild:
        try:
            manifest = build_index()
        except Exception as e:  # noqa: BLE001 — 검증 실패·임베딩 실패·건수 불일치 등 원인이 다양해 그대로 보고
            print(f"[indexing][오류] 색인 생성 실패: {e}")
            return 1
        print(f"[indexing] 색인 생성 완료: {json.dumps(manifest, ensure_ascii=False, indent=2)}")
        return 0

    if not args.validate_only:
        print("[indexing] --validate-only / --rebuild / --check-embedding 중 하나를 지정해야 함")
        return 2

    report = validate()
    _print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
