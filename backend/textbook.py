"""
교과서 자료 검색 세 가지 — 규칙 색인(backend/indexing.py · rag.search_rules, RAG 담당)과 별개의 컬렉션들.
(팀장 · 2026-09-14. 교수님 지적 "규칙은 모델이 이미 안다 → 검색이 지식을 보태지 않는다" 대응.
 RAG 담당이 나중에 indexing.py/rag.py 로 합쳐도 **함수 이름·반환 형식은 그대로** — tutor.py·ask.py 가 이 이름을 부른다.
 계약 문서: docs/2026.09.14 검색 함수 계약 (textbook·examples·faq).md)

    python -m backend.textbook --rebuild                 # 세 색인 전부 (교과서 862 · 틀린 예문 500 · FAQ 질문+변형 ~520)
    python -m backend.textbook --rebuild-textbook | --rebuild-examples | --rebuild-faq
    python -m backend.textbook --search "I go to school by bus." --level 3
    python -m backend.textbook --examples "i go bus"
    python -m backend.textbook --faq "왜 went 예요?"
    python -m backend.textbook --word "형이 영어로 뭐야?" --level 4   # 단어장 표 조회 (임베딩 없음)

세 함수 공통 약속
  - 임베딩은 backend/embedding.py 함수 그대로 (.env 의 EMBEDDING_BACKEND). 규칙 색인과 같은 모델이어야 같은 질의 벡터를 나눠 쓸 수 있다.
  - qvec 를 주면 임베딩을 다시 안 한다 (한 문장에 임베딩 1회로 여러 색인 조회).
  - 색인이 없거나 실패하면 예외 대신 빈 결과 + error 문자열 → /fix·/ask 를 막지 않는다.
  - 점수는 코사인(0~1). 절대 문턱은 두지 않는다 — 호출자가 분포(1위−5위 차이)로 판단.

  search_textbook(text, level, k_pattern, k_word)  → 교과서 패턴·단어 (학년 이하). /fix 의 "교과서 표현" 힌트 + 학년 밖 단어 후검사
  search_examples(text, level, k)                  → 틀린 예문(errors.jsonl + 규칙 wrong_example)으로 찾은 **규칙 후보**. /fix 가 rag.search_rules 와 번갈아 합침 (실측 hit@3 78% → 91%)
  search_faq(question, k, rule_id)                 → FAQ (질문 + 변형을 문장마다 색인). /ask 의 단어 겹침 매칭을 대신함
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from backend import embedding, golden, indexing

ROOT = Path(__file__).resolve().parent.parent
TEXT_VERSION = "textbook_v1|examples_v1|faq_v1|rulealias_v1"

# 색인 종류별 컬렉션 접두사·manifest (규칙 색인 manifest.json 과 같은 폴더)
_KINDS = {
    "textbook": {"prefix": "textbook_", "manifest": indexing.CHROMA_DIR / "textbook_manifest.json"},
    "examples": {"prefix": "examples_", "manifest": indexing.CHROMA_DIR / "examples_manifest.json"},
    "faq": {"prefix": "faq_", "manifest": indexing.CHROMA_DIR / "faq_manifest.json"},
    "rulealias": {"prefix": "rulealias_", "manifest": indexing.CHROMA_DIR / "rulealias_manifest.json"},   # 규칙 이름·요약·"X가 뭐예요?" 별칭 → 규칙 (문서는 rules.jsonl 그대로, 찾는 열쇠만 늘림)
}
MANIFEST_PATH = _KINDS["textbook"]["manifest"]   # 하위 호환 (관리자 /admin/textbook 이 읽음)
COLLECTION_PREFIX = _KINDS["textbook"]["prefix"]


# ── 문서 만들기 ─────────────────────────────────────────────────────────────
def _docs_textbook() -> list[dict]:
    """패턴 462 + 단어 400. golden.all_patterns()/all_words() 는 units.csv 의 레벨(3학년뿐)만 돌아 4~6학년이 빠지므로 CSV 를 직접 읽는다."""
    out = []
    for p in golden._read("patterns.csv"):  # noqa: SLF001
        out.append({"id": p["id"], "doc": p["text"], "meta": {"kind": "pattern", "level": int(p.get("level") or 0), "unit": p.get("unit", ""),
                                                             "rule_id": p.get("rule_id", ""), "meaning": p.get("meaning", ""), "tip": p.get("tip", "")}})
    for w in golden._read("words.csv"):  # noqa: SLF001
        out.append({"id": w["id"], "doc": f"{w['word']} — {w.get('example', '')}".strip(" —"),
                    "meta": {"kind": "word", "level": int(w.get("level") or 0), "unit": w.get("unit", ""), "word": w["word"],
                             "meaning": w.get("meaning", ""), "example": w.get("example", "")}})
    return out


def _docs_examples() -> list[dict]:
    """틀린 예문 → 규칙: errors.jsonl 의 error 400 + rules.jsonl 의 wrong_example 100. 학생 문장(틀린 영어)과 같은 종류라 규칙 설명문보다 잘 맞는다."""
    out = []
    for e in golden.errors():
        if e.get("error") and e.get("rule_id"):
            out.append({"id": e["id"], "doc": e["error"], "meta": {"rule_id": e["rule_id"], "unit": e.get("unit", ""), "source": "errors",
                                                                    "fix": e.get("fix", ""), "correct": e.get("correct", "")}})
    for r in golden.rules():
        if r.get("wrong_example"):
            out.append({"id": f"{r['id']}:wrong", "doc": r["wrong_example"], "meta": {"rule_id": r["id"], "unit": r.get("unit", ""), "source": "rule", "fix": "", "correct": ""}})
    return out


def _docs_faq() -> list[dict]:
    """FAQ 질문 + 변형(variants)을 문장마다 따로 색인하되, 문서 본문은 "질문 — 답" 으로 (답을 붙이면 뜻이 또렷해짐 —
    9/14 홀드아웃 실측 130문항: 질문만 hit@3 63% → 질문+답 78%). 검색 결과의 answer 는 golden.faqs() 에서 붙인다."""
    out = []
    for f in golden.faqs():
        qs = [f.get("question", "")] + list(f.get("variants") or [])
        ans = (f.get("answer") or "").strip()
        for i, q in enumerate(q for q in qs if q):
            out.append({"id": f"{f['id']}#{i}", "doc": f"{q} — {ans}" if ans else q, "question": q,
                        "meta": {"faq_id": f["id"], "unit": f.get("unit", ""), "rule_ids": ",".join(f.get("rule_ids") or []), "q": q}})
    return out


def _rule_term(rule_type: str) -> str:
    """규칙 이름에서 용어만: "과거시제(시간)" → "과거시제", "관사(a,an) 구별" → "관사 구별"."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", rule_type or "")).strip()


def _docs_rulealias() -> list[dict]:
    """규칙 별칭 색인 (2026-09-14 시험): 규칙마다 ① 이름(type) ② 요약(short) ③ "X가 뭐예요?" ④ "X 뜻" ⑤ 설명문 첫 문장 을 따로 색인.
    "과거시제가 뭐예요?" 같은 용어 질문은 규칙 설명문(영어 예문 위주) 임베딩으로는 0.83 에 그쳐 문턱을 못 넘는데, 이름·요약은 질문과
    같은 말이라 잘 맞는다. 답은 여기서 안 만들고 rules.jsonl 문서(text·examples)로 LLM 이 짓는다 — FAQ 줄을 늘리는 것과 다른 점.
    RAG 담당의 rules 색인(설명문 본문)과는 별개 컬렉션(rulealias_*)."""
    out = []
    for r in golden.rules():
        term = _rule_term(r.get("type", ""))
        first = re.split(r"(?<=[.요다])\s", (r.get("text") or "").strip(), maxsplit=1)[0]
        aliases = [r.get("type", ""), r.get("short", ""), f"{term}가 뭐예요?", f"{term} 뜻이 뭐예요?", first]
        for i, a in enumerate(a for a in aliases if a and a.strip()):
            out.append({"id": f"{r['id']}#{i}", "doc": a.strip(), "meta": {"rule_id": r["id"], "unit": r.get("unit", ""), "alias": a.strip()[:80]}})
    return out


_DOCS = {"textbook": _docs_textbook, "examples": _docs_examples, "faq": _docs_faq, "rulealias": _docs_rulealias}


# ── 색인 만들기 / 읽기 (공통) ──────────────────────────────────────────────
def _data_hash(docs: list[dict]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps([(d["id"], d["doc"]) for d in docs], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load_manifest(kind: str = "textbook") -> dict | None:
    p = _KINDS[kind]["manifest"]
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def build_index(kind: str = "textbook", batch: int = 50, sleep: float = 0.0) -> dict:
    """색인 생성 뒤 manifest 원자적 교체, 옛 컬렉션 삭제 — 규칙 색인과 같은 방식."""
    docs = _DOCS[kind]()
    if not docs:
        raise RuntimeError(f"{kind}: 색인할 자료가 없음")
    vectors: list[list[float]] = []
    for i in range(0, len(docs), batch):
        vectors += embedding.embed_documents([d["doc"] for d in docs[i:i + batch]])
        if sleep:
            time.sleep(sleep)
    if len(vectors) != len(docs):
        raise RuntimeError(f"{kind}: 임베딩 수({len(vectors)}) != 문서 수({len(docs)})")
    client = indexing._chroma_client()  # noqa: SLF001 — 규칙 색인과 같은 Chroma 저장소
    prefix = _KINDS[kind]["prefix"]
    name = f"{prefix}{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    try:
        for i in range(0, len(docs), 100):
            chunk = docs[i:i + 100]
            col.add(ids=[d["id"] for d in chunk], embeddings=vectors[i:i + 100], documents=[d["doc"] for d in chunk], metadatas=[d["meta"] for d in chunk])
        if col.count() != len(docs):
            raise RuntimeError(f"{kind}: 색인 건수 불일치 {col.count()} vs {len(docs)}")
    except Exception:
        client.delete_collection(name)
        raise
    manifest = {"kind": kind, "active_collection": name, "provider": embedding.EMBEDDING_PROVIDER, "model": embedding.EMBEDDING_MODEL, "dim": len(vectors[0]),
                "distance": "cosine", "text_version": TEXT_VERSION, "count": len(docs), "data_hash": _data_hash(docs),
                "generated_at": datetime.now().isoformat(timespec="seconds")}
    if kind == "textbook":
        manifest["patterns"] = sum(1 for d in docs if d["meta"]["kind"] == "pattern")
        manifest["words"] = sum(1 for d in docs if d["meta"]["kind"] == "word")
    if kind == "faq":
        manifest["faqs"] = len({d["meta"]["faq_id"] for d in docs})
    if kind == "rulealias":
        manifest["rules"] = len({d["meta"]["rule_id"] for d in docs})
    mp = _KINDS[kind]["manifest"]
    tmp = mp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(mp)
    for c in client.list_collections():
        if c.name.startswith(prefix) and c.name != name:
            client.delete_collection(c.name)
    return manifest


def _query(kind: str, qvec: list[float], k: int, where: dict | None = None) -> list[tuple[str, str, dict, float]]:
    """(id, document, metadata, score) 목록. 색인 없으면 예외 (호출자가 빈 결과로 바꿈)."""
    m = load_manifest(kind)
    if not m:
        raise RuntimeError(f"{kind} 색인 없음 — python -m backend.textbook --rebuild-{kind}")
    col = indexing._chroma_client().get_collection(m["active_collection"])  # noqa: SLF001
    kw = {"query_embeddings": [qvec], "n_results": max(1, k), "include": ["documents", "metadatas", "distances"]}
    if where:
        kw["where"] = where
    res = col.query(**kw)
    return [(id_, doc, meta, round(1 - dist, 4)) for id_, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])]


# ── ① 교과서 패턴·단어 ─────────────────────────────────────────────────────
_EMPTY = {"patterns": [], "words": [], "query_ms": 0, "error": None}


def search_textbook(text: str, level: int = 3, k_pattern: int = 3, k_word: int = 5, min_score: float = 0.0, qvec: list[float] | None = None) -> dict:
    """학생 문장에 가까운 교과서 패턴·단어 (학년 이하만).
    반환 {"patterns": [{id,text,meaning,tip,rule_id,unit,level,score}], "words": [{id,word,meaning,example,unit,level,score}], "query_ms", "error"}."""
    t0 = time.perf_counter()
    try:
        q = qvec or embedding.embed_query(text)
        out = {"patterns": [], "words": [], "error": None}
        for kind, k in (("pattern", k_pattern), ("word", k_word)):
            if k <= 0:
                continue
            for id_, doc, meta, score in _query("textbook", q, k, {"$and": [{"kind": kind}, {"level": {"$lte": int(level)}}]}):
                if score < min_score:
                    continue
                if kind == "pattern":
                    out["patterns"].append({"id": id_, "text": doc, "meaning": meta.get("meaning", ""), "tip": meta.get("tip", ""), "rule_id": meta.get("rule_id", ""),
                                            "unit": meta.get("unit", ""), "level": meta.get("level"), "score": score})
                else:
                    out["words"].append({"id": id_, "word": meta.get("word", ""), "meaning": meta.get("meaning", ""), "example": meta.get("example", ""),
                                         "unit": meta.get("unit", ""), "level": meta.get("level"), "score": score})
        out["query_ms"] = int((time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:  # noqa: BLE001
        return {**_EMPTY, "query_ms": int((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:120]}"}


def known_words(level: int) -> set[str]:
    """학년 이하 교과서에 나온 말 (소문자): 단어장 표제어 + 단어장 예문·패턴 문장에 쓰인 낱말. 고친 문장에 교과서 밖 단어가 있는지 표시하는 후검사용.
    표제어만 보면 "We saw a lion at the zoo."(3학년 예문)의 saw 도 새 단어로 찍혀서, 예문·패턴 문장의 낱말까지 넣는다."""
    lv = int(level)
    out: set[str] = set()
    for w in golden._read("words.csv"):  # noqa: SLF001
        if int(w.get("level") or 0) <= lv:
            out.add(w["word"].strip().lower())
            out.update(re.findall(r"[a-z']+", (w.get("example") or "").lower()))
    for p in golden._read("patterns.csv"):  # noqa: SLF001
        if int(p.get("level") or 0) <= lv:
            out.update(re.findall(r"[a-z']+", (p.get("text") or "").lower()))
    return {t.strip("'") for t in out if t.strip("'")}


# ── ② 틀린 예문 → 규칙 후보 ──────────────────────────────────────────────
def search_examples(text: str, level: int | None = None, k: int = 5, qvec: list[float] | None = None) -> list[dict]:
    """학생 문장과 닮은 틀린 예문을 찾아 **규칙 후보**로 돌려준다 (규칙마다 가장 닮은 예문 하나, 점수 내림차순, k개).
    반환 [{id: "R-09", type, text(규칙 설명문), unit, score, example_id: "E-0035", example: "…", fix: "…"}] — rag.search_rules 와 같은 키 + 예문 정보.
    level 은 지금은 안 씀(예문에 학년이 없음) — 시그니처만 예약. 색인 없으면 []."""
    try:
        q = qvec or embedding.embed_query(text)
        rules = {r["id"]: r for r in golden.rules()}
        best: dict[str, tuple[float, str, str, dict]] = {}
        for id_, doc, meta, score in _query("examples", q, max(k * 4, 20)):        # 같은 규칙의 예문이 여럿 나오므로 넉넉히 뽑아 규칙별로 접는다
            rid = meta.get("rule_id")
            if rid in rules and (rid not in best or score > best[rid][0]):
                best[rid] = (score, id_, doc, meta)
        out = []
        for rid, (score, eid, doc, meta) in sorted(best.items(), key=lambda x: -x[1][0])[:k]:
            r = rules[rid]
            out.append({"id": rid, "type": r["type"], "text": r["text"], "unit": r.get("unit", ""), "score": score,
                        "example_id": eid, "example": doc, "fix": meta.get("fix", ""), "correct": meta.get("correct", "")})
        return out
    except Exception:  # noqa: BLE001
        return []


def similar_examples(text: str, rule_id: str, k: int = 3, qvec: list[float] | None = None, exclude_text: str = "") -> list[dict]:
    """한 규칙의 틀린 예문 중 학생 문장과 닮은 순 (errors.jsonl 행 우선, 규칙의 wrong_example 은 뒤로, 학생 문장과 같은 예문 제외).
    /fix 의 peer_example(화면 🙋 타일 · 오답노트 연습 문제)용. 반환 [{example_id, example, fix, correct, score}]."""
    try:
        q = qvec or embedding.embed_query(text)
        norm = lambda t: " ".join(str(t or "").lower().replace(".", "").replace("!", "").replace("?", "").split())
        out = []
        for id_, doc, meta, score in _query("examples", q, max(k * 3, 6), {"rule_id": rule_id}):
            if norm(doc) == norm(exclude_text):
                continue
            out.append({"example_id": id_, "example": doc, "fix": meta.get("fix", ""), "correct": meta.get("correct", ""), "score": score,
                        "_rank": (0 if meta.get("source") == "errors" else 1, -score)})
        out.sort(key=lambda x: x["_rank"])
        return [{k2: v for k2, v in o.items() if k2 != "_rank"} for o in out[:k]]
    except Exception:  # noqa: BLE001
        return []


def merge_candidates(by_examples: list[dict], by_rules: list[dict], k: int = 5) -> list[dict]:
    """예문 후보와 규칙 설명문 후보를 번갈아 합친다 (예문1, 규칙1, 예문2, 규칙2 …, 같은 규칙은 한 번). /fix 가 프롬프트 후보 5개를 만들 때.
    각 항목에 from: 'examples' | 'rules' 를 붙인다 — 실측(9/14, 300문장): 설명문만 hit@3 78% → 합침 91%."""
    out, seen = [], set()
    for pair in zip(by_examples + [None] * len(by_rules), by_rules + [None] * len(by_examples)):
        for c, src in ((pair[0], "examples"), (pair[1], "rules")):
            if c and c["id"] not in seen:
                seen.add(c["id"]); out.append({**c, "from": src})
    return out[:k]


# ── ③ FAQ (물어보기) ───────────────────────────────────────────────────────
def search_faq(question: str, k: int = 3, rule_id: str | None = None, qvec: list[float] | None = None) -> list[dict]:
    """학생 질문과 닮은 FAQ (질문+변형 중 가장 닮은 문장 기준, FAQ 하나에 한 줄). 직전 규칙(rule_id)과 관련된 FAQ 는 +0.03 가산.
    반환 [{id: "F-012", question, answer, rule_ids: [...], unit, example, score, matched: "닮은 질문 변형"}]. 색인 없으면 []."""
    try:
        import re as _re
        q = qvec or embedding.embed_query(question)
        faqs = {f["id"]: f for f in golden.faqs()}
        # 영어 낱말(can, s, will, the …)은 임베딩이 뭉개기 쉬워서, 질문의 영어 토큰이 FAQ 질문·변형에 그대로 있으면 토큰당 +0.02 (동점 깨기용, 최대 +0.06)
        # 9/14 "can 뒤에 s 를 쓸 수 있어?" → 임베딩만으론 will(0.862)·one(0.860)·can(0.859) 순으로 평평했음
        eng = {t.lower() for t in _re.findall(r"[A-Za-z][A-Za-z']*", question) if len(t) >= 1}
        best: dict[str, tuple[float, str]] = {}
        for id_, doc, meta, score in _query("faq", q, max(k * 4, 15)):
            fid = meta.get("faq_id")
            if fid not in faqs:
                continue
            if rule_id and rule_id in (meta.get("rule_ids") or "").split(","):
                score = round(score + 0.03, 4)
            if eng:
                qtoks = {t.lower() for t in _re.findall(r"[A-Za-z][A-Za-z']*", meta.get("q") or doc)}
                score = round(score + min(0.06, 0.02 * len(eng & qtoks)), 4)
            if fid not in best or score > best[fid][0]:
                best[fid] = (score, meta.get("q") or doc)
        out = []
        for fid, (score, matched) in sorted(best.items(), key=lambda x: -x[1][0])[:k]:
            f = faqs[fid]
            out.append({"id": fid, "question": f.get("question", ""), "answer": f.get("answer", ""), "rule_ids": list(f.get("rule_ids") or []),
                        "unit": f.get("unit", ""), "example": f.get("example", ""), "score": score, "matched": matched})
        return out
    except Exception:  # noqa: BLE001
        return []


def faq_hit(scores: list[float], top: float = 0.85) -> bool:
    """FAQ 는 질문 형식이 다 비슷해 점수 분포가 늘 촘촘하다(정답이 있어도 1위−3위 0.01). 그래서 FAQ 만은 1위 절대 점수로 판정:
    9/14 실측 — 정답 있음: "can 뒤에 s" 0.899 · "will 뒤에 ing" 0.937 · "형용사 앞에" 0.878 / 엉뚱한 "점심 뭐 먹지" 0.804. 기준 0.85 (RAG 담당이 시험지로 조정)."""
    return bool(scores) and scores[0] >= top


def sharp(scores: list[float], gap: float = 0.06, top: float = 0.85) -> bool:
    """점수 분포가 뾰족한가 — "닮은 것이 진짜 있다"의 임시 판정 (1위 ≥ top 이고 1위−5위 ≥ gap). RAG 담당이 실측으로 다듬을 값."""
    if not scores:
        return False
    return scores[0] >= top and (scores[0] - scores[min(4, len(scores) - 1)]) >= gap


# ── ⑦ 쌍둥이 규칙 (rules.jsonl 의 related 열) ─────────────────────────────
def rule_family(rule_id: str) -> set[str]:
    """규칙 id 와 그 짝(rules.jsonl 의 `related` 열, 없으면 빈 목록)을 한 묶음으로. 교과서가 같은 문법을 단원마다 다른 이름으로 부르는 일이 있어
    (명사복수형 R-33 ↔ 숫자+복수명사 R-12) 짝은 결함이 아니라 데이터에 적어 두는 사실 (2026-09-15 팀장 결정). 채점은 짝 중 어느 쪽이든 정답,
    화면·/ask 는 "비슷한 규칙" 안내에 쓴다. 양방향으로 본다 (한쪽에만 적혀 있어도 됨)."""
    rid = (rule_id or "").strip()
    if not rid:
        return set()
    fam = {rid}
    for r in golden.rules():
        rel = [x.strip() for x in (r.get("related") or []) if x and x.strip()]
        if r["id"] == rid:
            fam.update(rel)
        elif rid in rel:
            fam.add(r["id"])
    return fam


# ── ⑥ 단어장 표 조회 (임베딩 없음) ──────────────────────────────────────
_WORD_BY_EN: dict[str, list[dict]] = {}      # "bus" → [단어장 행, …]
_WORD_BY_KO: dict[str, list[dict]] = {}      # "형" → [단어장 행, …]  (뜻 열 "형/오빠/남동생" 을 슬래시로 나눠 각각 열쇠)


def _word_tables() -> tuple[dict, dict]:
    if not _WORD_BY_EN:
        for w in golden._read("words.csv"):  # noqa: SLF001
            row = {**w, "level": int(w.get("level") or 0)}
            _WORD_BY_EN.setdefault(w["word"].strip().lower(), []).append(row)
            for ko in re.split(r"[/,·]", w.get("meaning", "") or ""):
                ko = ko.strip()
                if ko:
                    _WORD_BY_KO.setdefault(ko, []).append(row)
    return _WORD_BY_EN, _WORD_BY_KO


def lookup_word(question: str, level: int = 6) -> list[dict]:
    """질문 속 낱말을 단어장(words.csv)에서 **글자로** 찾는다 — 임베딩 검색이 아니라 키워드 검색 (하이브리드 검색의 키워드 쪽).
    ① 영어 낱말 → 뜻 ("bus 가 뭐야?") ② 한국어 뜻 → 영어 ("형이 영어로 뭐야?" → w-0024 brother). 변형(-s/-es/-ing/-ed)은 끝을 떼고 다시 찾는다.
    반환은 search_textbook 의 words 항목과 같은 모양 [{id, word, meaning, example, unit, level, score=1.0}] 이라 ask.py 가 그 자리에 그대로 쓴다.
    학년(level) 이하 행을 우선하되 없으면 전체. 2026-09-15 TTS 담당 수정 목록 4번(단어장 역방향 조회)용. words 임베딩 400건은 이걸로 대체 예정."""
    by_en, by_ko = _word_tables()
    hits: list[dict] = []
    for tok in re.findall(r"[a-z']+", question.lower()):
        if len(tok) < 2:
            continue
        for cand in (tok, re.sub(r"(ies)$", "y", tok), re.sub(r"(es|s|ing|ed)$", "", tok)):
            if cand in by_en:
                hits += by_en[cand]
                break
    for ko in sorted(by_ko, key=len, reverse=True):           # 긴 뜻부터: "할머니" 가 "머니" 보다 먼저 맞도록
        if ko in question:
            hits += by_ko[ko]
    lv = int(level or 0)
    if lv:
        hits = [h for h in hits if h["level"] <= lv] or hits
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        if h["id"] not in seen:
            seen.add(h["id"])
            out.append({"id": h["id"], "word": h["word"], "meaning": h.get("meaning", ""), "example": h.get("example", ""),
                        "unit": h.get("unit", ""), "level": h["level"], "score": 1.0})
    return out


# ── ⑤ 규칙 별칭 → 규칙 (문법 용어 질문) ─────────────────────────────────
def search_rule_aliases(question: str, k: int = 3, qvec: list[float] | None = None) -> list[dict]:
    """"과거시제가 뭐예요?" 류 질문 → 규칙 후보 (규칙마다 가장 닮은 별칭 하나, 점수 내림차순).
    반환 [{id, type, short, text, examples, unit, score, matched}] — 답 재료는 text·examples (rules.jsonl 문서). 색인 없으면 []."""
    try:
        q = qvec or embedding.embed_query(question)
        rules = {r["id"]: r for r in golden.rules()}
        best: dict[str, tuple[float, str]] = {}
        for id_, doc, meta, score in _query("rulealias", q, max(k * 5, 15)):
            rid = meta.get("rule_id")
            if rid in rules and (rid not in best or score > best[rid][0]):
                best[rid] = (score, doc)
        out = []
        for rid, (score, doc) in sorted(best.items(), key=lambda x: -x[1][0])[:k]:
            r = rules[rid]
            out.append({"id": rid, "type": r.get("type", ""), "short": r.get("short", ""), "text": r.get("text", ""), "examples": r.get("examples") or [],
                        "unit": r.get("unit", ""), "score": score, "matched": doc})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"[rulealias] 검색 실패: {type(e).__name__}: {e}", flush=True)
        return []


def rule_hit(scores: list[float], top: float = 0.86) -> bool:
    """규칙 별칭 검색 "있다" 판정 (절대 점수). 2026-09-14 실측: 용어 질문 12개 중 11개가 0.864~0.927, 용어 아닌 질문 11개는 0.79~0.845 (관련 규칙이 진짜 있던 1개만 0.877)."""
    return bool(scores) and scores[0] >= top


# ── CLI ────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="세 색인 전부")
    for kind in _KINDS:
        ap.add_argument(f"--rebuild-{kind}", action="store_true")
    ap.add_argument("--search", default=None, help="교과서 패턴·단어 검색")
    ap.add_argument("--examples", default=None, help="틀린 예문 → 규칙 후보")
    ap.add_argument("--faq", default=None, help="FAQ 검색")
    ap.add_argument("--rule", default=None, help="규칙 별칭 검색 (문법 용어 질문)")
    ap.add_argument("--word", default=None, help="단어장 표 조회 (임베딩 없음): 영어 낱말 → 뜻, 한국어 뜻 → 영어")
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=0.0, help="배치 사이 대기 초 (gemini 한도용)")
    args = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    did = False
    for kind in _KINDS:
        if args.rebuild or getattr(args, f"rebuild_{kind}"):
            m = build_index(kind, sleep=args.sleep); did = True
            print(f"[{kind}] 색인 완료: {m['count']}건 · {m['provider']} {m['model']} dim {m['dim']} · {m['active_collection']}")
    if args.search:
        r = search_textbook(args.search, level=args.level); did = True
        print(f"[textbook] '{args.search}' level<={args.level} · {r['query_ms']}ms" + (f" · 오류 {r['error']}" if r["error"] else ""))
        for p in r["patterns"]:
            print(f"  패턴 {p['score']:.3f} {p['id']} L{p['level']} {p['unit']} | {p['text']} ({p['meaning']})")
        for w in r["words"]:
            print(f"  단어 {w['score']:.3f} {w['id']} L{w['level']} {w['unit']} | {w['word']} ({w['meaning']})")
    if args.examples:
        did = True
        for c in search_examples(args.examples, k=5):
            print(f"  규칙 {c['score']:.3f} {c['id']} {c['type']} | 닮은 예문 {c['example_id']}: {c['example']} → {c['fix'] or c['correct']}")
    if args.faq:
        did = True
        for f in search_faq(args.faq, k=3):
            print(f"  FAQ {f['score']:.3f} {f['id']} | {f['question']} (닮은 변형: {f['matched']}) → {f['answer'][:60]}")
    if args.rule:
        did = True
        for r in search_rule_aliases(args.rule, k=3):
            print(f"  규칙 {r['score']:.3f} {r['id']} {r['type']} | 닮은 별칭: {r['matched']} | {r['short']}")
    if args.word:
        did = True
        rows = lookup_word(args.word, level=args.level)
        print(f"[word] '{args.word}' level<={args.level} → {len(rows)}건" + ("" if rows else " (없음)"))
        for w in rows:
            print(f"  단어 {w['id']} L{w['level']} {w['unit']} | {w['word']} ({w['meaning']}) 예: {w['example']}")
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
