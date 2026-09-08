"""
검색 평가 — 실행 단위 ③   담당: RAG 담당

python -m tests.eval_rag --retrieval-only

golden.eval_set() 문장으로 backend.rag.search_rules() 를 실제로 호출해 hit@1·hit@3 를 측정한다.
NONE(정상 문장 2개)은 hit@1/hit@3 분모에서 제외하지만, 검색 자체는 정상 문장에도 수행해 1위 점수를
참고용으로 같이 기록한다 — 이 결과만으로 "정상 문장을 오탐하는지"는 판정하지 않는다(생성까지 붙어야
판정 가능, 실행 단위 ④ 이후). 검색 실패(색인 없음·예외)는 분모에서 빼지 않고 해당 문장을 miss 로
집계한 뒤 실패 사유를 별도로 남긴다.

결과는 data/rag_eval/(git 제외)에 저장한다:
    retrieval_eval_<시각>.json   문장별 상세
    retrieval_eval_latest.json  가장 최근 실행의 복사본 (GET /api/rag/eval 이 읽는 파일)

tests/eval_fix.py(생성 모델 비교)와는 별개다 — 그 결과를 검색 지표로 재사용하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import golden, indexing, rag                             # noqa: E402

OUT_DIR = indexing.RAG_EVAL_DIR
LATEST_PATH = indexing.RETRIEVAL_EVAL_LATEST
K = 3


def run_retrieval_eval() -> dict:
    rows_in = golden.eval_set()
    try:
        manifest = indexing.load_manifest()
        index_info = {
            "active_collection": manifest["active_collection"],
            "provider": manifest["provider"],
            "model": manifest["model"],
            "dim": manifest["dim"],
            "distance": manifest["distance"],
        }
        data_hash = manifest["data_hash"]
    except indexing.IndexUnavailableError as e:
        index_info, data_hash = None, None
        print(f"[eval_rag][경고] 색인 없음 — 전체 문장이 실패로 집계됨: {e}")

    detail = []
    hit1_n = hit3_n = error_n = normal_n = search_failures = 0

    for row in rows_in:
        text = (row.get("text") or "").strip()
        expected = (row.get("expected_rule_id") or "").strip()
        is_normal = expected == "NONE"
        if is_normal:
            normal_n += 1
        else:
            error_n += 1

        t0 = time.perf_counter()
        try:
            candidates = rag.search_rules(text, k=K)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            top_ids = [c["id"] for c in candidates]
            hit1 = (not is_normal) and bool(top_ids) and top_ids[0] == expected
            hit3 = (not is_normal) and expected in top_ids
            if not is_normal:
                hit1_n += int(hit1)
                hit3_n += int(hit3)
            detail.append({
                "text": text, "expected_rule_id": expected, "is_normal": is_normal,
                "candidates": candidates, "hit_at_1": hit1, "hit_at_3": hit3,
                "ms": ms, "error": None,
            })
        except Exception as e:  # noqa: BLE001 — 색인 없음·연결 실패 등 실패 사유를 그대로 문장별로 남긴다
            ms = round((time.perf_counter() - t0) * 1000, 1)
            if not is_normal:
                search_failures += 1   # 분모(error_n)에서 빼지 않고 miss 로만 집계 — 실패를 조용히 숨기지 않는다
            detail.append({
                "text": text, "expected_rule_id": expected, "is_normal": is_normal,
                "candidates": [], "hit_at_1": False, "hit_at_3": False,
                "ms": ms, "error": f"{type(e).__name__}: {e}",
            })

    hit_at_1 = round(hit1_n / error_n, 4) if error_n else None
    hit_at_3 = round(hit3_n / error_n, 4) if error_n else None

    result = {
        "n": error_n,                     # 기존 계약: n = 오류 문장 수(검색 적중률 분모)
        "total_n": len(rows_in),
        "normal_n": normal_n,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "threshold": None,
        "search_failures": search_failures,
        "k": K,
        "index": index_info,
        "data_hash": data_hash,
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "runs": [{"label": f"{index_info['model']}" if index_info else "색인 없음", "hit_at_1": hit_at_1, "hit_at_3": hit_at_3}],
        "rows": detail,
    }
    return result


def _print_summary(result: dict) -> None:
    print(f"[eval_rag] 대상 {result['total_n']}문장 (오류 {result['n']} · 정상 {result['normal_n']}) · 검색 실패 {result['search_failures']}건")
    print(f"[eval_rag] hit@1 = {result['hit_at_1']}  hit@3 = {result['hit_at_3']}  (목표 hit@3 ≥ 0.80 — 조작하지 않음, n={result['n']}으로 표본이 작음)")
    for row in result["rows"]:
        mark = "OK " if row["hit_at_3"] else ("--- " if row["is_normal"] else "MISS")
        top = row["candidates"][0] if row["candidates"] else None
        top_desc = f"{top['id']}({top['score']})" if top else (row["error"] or "결과 없음")
        print(f"  [{mark}] {row['expected_rule_id'] or 'NONE':6s} {row['text'][:40]:40s} → 1위 {top_desc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only", action="store_true", help="검색 평가만 실행 (생성 평가는 실행 단위 ④ 대상, 이 파일에 아직 없음)")
    args = parser.parse_args(argv)

    if not args.retrieval_only:
        print("[eval_rag] --retrieval-only 를 지정해야 함 (생성 평가 --with-generation 은 팀장 tutor.py 연결 후 실행 단위 ④에서 추가 예정)")
        return 2

    result = run_retrieval_eval()
    _print_summary(result)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_path = OUT_DIR / f"retrieval_eval_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    text = json.dumps(result, ensure_ascii=False, indent=2)
    ts_path.write_text(text, encoding="utf-8")
    LATEST_PATH.write_text(text, encoding="utf-8")
    print(f"[eval_rag] 저장: {ts_path.name} (및 retrieval_eval_latest.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
