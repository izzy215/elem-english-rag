"""
튜터 — 내 문장 고쳐주기 (PRD 4.3)   담당: 팀장

POST /api/fix  {student, level, unit, text, source}
  → {ok, rule, runner_up, wrong, fix, fixed, why, source, more_errors, suggested_questions, mission, log_id, mode}

동작:
  1. RAG 검색(rag.search_rules) 으로 학생 문장과 가장 가까운 규칙 상위 3개 → 1위 조각만 프롬프트에 (mode="rag")
     검색 실패(색인 없음·임베딩 오류)면 규칙 전부를 프롬프트에 (mode="fallback", fallback_reason="search_error")
  2. 오늘의 미션(units.csv)과 함께 프롬프트(prompts/fix_fallback.txt)에 넣어 LLM(backend/llm.py) 에 JSON 으로만 답하게 한다
  3. 모델이 답한 규칙 id 가 '전달한 근거 안' 에 있는지 검증 (밖이면 502). 근거·점수는 서버가 전달한 후보에서 구성
  4. 학생 DB 에 문장 로그 + 오답노트 기록 (fix_internal() 은 기록 없이 같은 결과 — 평가용)

threshold 는 아직 미설정 (RAG 담당 실측: 정상 문장이 오류 문장보다 검색 점수가 높음). 정오 판단은 모델의 ok 가 한다.
화면(frontend/js/tutor.js)은 이 응답 형식을 이미 기다리고 있다. 필드 이름을 바꾸면 화면도 같이 바꿔야 한다.

데이터 읽기는 전부 golden.py (TTS 팀원 소유, 공통): rules() · find_rule() · find_unit(). 골든/샘플 선택도 거기서 한다.
학생 DB: data/student/sentence_log.jsonl, notebook.json (PRD 5.2 형식, gitignore)
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import golden, llm
from backend.config import settings

ROOT = Path(__file__).resolve().parent.parent          # project/
STUDENT_DIR = ROOT / "data" / "student"
PROMPT_FILE = Path(__file__).parent / "prompts" / "fix_fallback.txt"

router = APIRouter(tags=["tutor"])
_lock = threading.Lock()
RAG_TOP_K = 5          # 프롬프트에 넣는 검색 후보 수. 1 = 인계문서 최초 기준선(1위만). 어순 규칙(R-09)은 임베딩이 순서를 못 봐서 4~5위로 나와 5 로 둔다 (규칙 38개가 들어오면 다시 조정)


# ─────────────────────────────────────────────
# 프롬프트 · Gemini
# ─────────────────────────────────────────────
def _render(template: str, **vars_: str) -> str:
    for k, v in vars_.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def _rules_block(rule_list: list[dict]) -> str:
    return "\n".join(f"- [{r['id']}] {r['type']}: {r['text']}" for r in rule_list)


def _ask_llm(prompt: str) -> dict:
    """JSON 만 받는다. 어느 모델(Gemini/로컬)을 쓸지는 backend/llm.py 와 .env 의 LLM_BACKEND 가 정한다."""
    return llm.generate_json(prompt)


def _single_fix(text: str, wrong: str | None, fix: str | None) -> str | None:
    """학생 문장에서 wrong 한 단어(구)만 fix 로 바꾼 문장. wrong 이 문장에 없으면 None.
    Gemini 가 지시를 어기고 여러 곳을 한꺼번에 고쳐 와도, 화면에는 '1위 규칙 하나만 고친 문장' 을 보여 주기 위해 서버가 다시 만든다.
    그래야 [다시 고쳐줘] 2차에서 나머지 오류가 실제로 잡힌다 (PRD 7: 1위만 고치고 more_errors)."""
    if not wrong or not fix:
        return None
    m = re.search(r"(?<![A-Za-z])" + re.escape(wrong.strip()) + r"(?![A-Za-z])", text, flags=re.IGNORECASE)
    if not m:
        return None
    out = text[: m.start()] + fix.strip() + text[m.end():]
    out = out.strip()
    out = out[0].upper() + out[1:]                       # 문장 첫 글자 대문자 (문법 아님, 보기용)
    if out and out[-1] not in ".!?":
        out += "."
    return out


_ARTICLES = {"a", "an", "the"}
# 불규칙 변화 (어간이 안 겹치는 것들). 그 외 한 단어 교체는 어간(앞 2글자)이 같아야 "같은 단어의 변형" 으로 본다
_IRREGULAR = {"go": {"went", "goes", "going"}, "see": {"saw", "sees", "seeing"}, "eat": {"ate", "eats", "eating"}, "have": {"had", "has", "having"},
              "do": {"did", "does", "doing"}, "am": {"was", "is", "are"}, "is": {"was", "am", "are"}, "are": {"were", "am", "is"}, "was": {"were", "am", "is"},
              "were": {"was", "are"}, "be": {"am", "is", "are", "was", "were"}, "run": {"ran"}, "come": {"came"}, "take": {"took"}, "give": {"gave"},
              "make": {"made"}, "get": {"got"}, "buy": {"bought"}, "drink": {"drank"}, "swim": {"swam"}, "sing": {"sang"},
              "a": {"an", "the"}, "an": {"a", "the"}, "the": {"a", "an"}, "child": {"children"}, "man": {"men"}, "woman": {"women"}, "foot": {"feet"}, "tooth": {"teeth"}, "mouse": {"mice"}}
_TIME_WORDS = {"yesterday", "today", "tomorrow", "now", "ago", "last", "next", "week", "year", "month", "morning", "night"}   # 우리 규칙은 시간 표현을 바꾸지 않는다


def _tokens(t: str) -> list[str]:
    return re.findall(r"[a-z']+", (t or "").lower())


def _pair_problem(text: str, wrong: str | None, fix: str | None, rule_type: str = "") -> str | None:
    """모델이 준 (wrong → fix) 쌍이 '한 단어를 규칙에 맞게 바꾼 것' 인지 확인. 문제가 있으면 이유 문자열, 없으면 None.
    모델(특히 소형 모델)이 어순을 고치려고 wrong=yesterday fix=saw 같은 엉뚱한 쌍을 주면, 그대로 치환했을 때 'I saw saw lion' 이 된다."""
    if not wrong or not fix:
        return "wrong/fix 비어 있음"
    w, f = _tokens(wrong), _tokens(fix)
    if not w or not f:
        return "wrong/fix 가 단어가 아님"
    if not re.search(r"(?<![A-Za-z])" + re.escape(wrong.strip()) + r"(?![A-Za-z])", text, flags=re.IGNORECASE):
        return f"wrong={wrong!r} 이 학생 문장에 없음"
    if "어순" in (rule_type or ""):                          # 어순 규칙: 같은 단어들의 재배열만 허용 (관사는 넣거나 빼도 됨)
        strip = lambda ts: sorted(t for t in ts if t not in _ARTICLES)
        if len(w) < 2 or strip(w) != strip(f) or w == f:
            return f"어순 규칙인데 fix={fix!r} 가 wrong={wrong!r} 의 재배열이 아님"
        return None
    if len(w) != 1:
        return f"wrong 이 한 단어가 아님: {wrong!r}"
    if w[0] in _TIME_WORDS:
        return f"wrong={wrong!r} 은 시간 표현 (규칙이 바꾸는 대상이 아님 — 어순 변경 시도)"
    f_core = [x for x in f if x not in _ARTICLES]
    if len(f) > 1 and f_core != w:                       # 여러 단어면 '관사 + 원래 단어' 만 허용 (lion → a lion)
        return f"fix={fix!r} 가 관사 추가 형태가 아님"
    if len(f) == 1 and f[0] in _ARTICLES and w[0] not in _ARTICLES:   # saw → a 처럼 단어를 관사로 갈아치움
        return f"fix={fix!r} 가 wrong={wrong!r} 을 관사로 바꿈"
    if len(f) == 1 and f[0] != w[0]:
        others = _tokens(text)
        others.remove(w[0])
        if f[0] in others:                                # fix 가 문장 다른 곳에 이미 있음 → 어순 바꾸기 시도 (yesterday → saw)
            return f"fix={fix!r} 가 문장에 이미 있는 단어 (어순 변경 시도)"
        same_stem = f[0][:2] == w[0][:2] or f[0] in _IRREGULAR.get(w[0], set()) or w[0] in _IRREGULAR.get(f[0], set())
        if not same_stem:                                 # lastyear → yesterday 처럼 다른 단어로 갈아치움 (뜻이 바뀜)
            return f"fix={fix!r} 가 wrong={wrong!r} 의 변형이 아님 (다른 단어로 교체)"
    return None


def _full_fixed_ok(text: str, full_fixed: str, fix: str | None) -> bool:
    """full_fixed 가 학생 단어로만 이뤄졌는지. 관사·fix 단어 외에 새 단어가 2개 넘게 들어오거나 문장이 2단어 넘게 길어지면 거부."""
    src, dst = _tokens(text), _tokens(full_fixed)
    if not dst:
        return False
    allowed = set(src) | _ARTICLES | set(_tokens(fix or ""))
    new_words = [t for t in dst if t not in allowed]
    return len(new_words) <= 2 and len(dst) <= len(src) + 2


def _search_candidates(text: str, k: int = 3) -> tuple[list[dict], str, str | None]:
    """RAG 검색 (rag.py 의 search_rules, RAG 담당). 반환: (후보 목록 score 내림차순, mode, fallback_reason)
    - 검색 성공 → ([{id,type,text,unit,score}, …], "rag", None)
    - 색인 없음·임베딩/질의 실패(indexing.IndexUnavailableError) 나 그 외 예외 → ([], "fallback", "search_error")
    - 결과 0건 → ([], "fallback", "no_results")
    threshold 는 아직 안 건다: 실측에서 정상 문장이 오류 문장보다 점수가 높게 나와(0.415 vs 0.317) 점수로 정오를 가르면 역효과.
    정오 판단은 프롬프트·생성 모델의 ok 가 맡고, 검색은 '근거를 좁히는' 역할만 한다 (docs/RAG_0909/팀장-인계문서.md 3절)."""
    try:
        from backend import indexing
        from backend.rag import search_rules
    except ImportError as e:                                # rag.py/indexing.py 가 없는 환경
        print(f"[fix] 검색 모듈 없음 → 폴백: {e}", flush=True)
        return [], "fallback", "search_error"
    try:
        cands = search_rules(text, k=k)
    except indexing.IndexUnavailableError as e:
        print(f"[fix] 검색 불가 → 폴백: {e}", flush=True)
        return [], "fallback", "search_error"
    except Exception as e:                                   # 예상 밖 예외도 서비스는 살린다
        print(f"[fix] 검색 예외 → 폴백: {type(e).__name__}: {e}", flush=True)
        return [], "fallback", "search_error"
    if not cands:
        return [], "fallback", "no_results"
    return cands, "rag", None


# ─────────────────────────────────────────────
# 학생 DB (PRD 5.2)
# ─────────────────────────────────────────────
def _log_sentence(row: dict) -> None:
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, (STUDENT_DIR / "sentence_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _notebook_add(student: str, rule_id: str, log_id: str) -> None:
    """notebook.json  {"A":{"R-01":{"count":3,"last":"2026-09-10","streak":0,"log_ids":[...]}}}"""
    STUDENT_DIR.mkdir(parents=True, exist_ok=True)
    path = STUDENT_DIR / "notebook.json"
    with _lock:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = data.setdefault(student, {}).setdefault(rule_id, {"count": 0, "last": "", "streak": 0, "log_ids": []})
        entry["count"] += 1
        entry["last"] = datetime.now().strftime("%Y-%m-%d")
        entry["streak"] = 0                       # 또 틀렸으니 극복 진행 초기화
        entry["log_ids"] = (entry["log_ids"] + [log_id])[-10:]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
class FixIn(BaseModel):
    student: str = "A"
    level: int = 2
    unit: str = ""
    text: str
    source: str = "typed"           # "stt" | "typed"


def diagnose(text: str, level: int = 2, unit: str = "", student: str = "A", source_kind: str = "typed", record: bool = True) -> dict:
    """/fix 의 본체. record=False 면 sentence_log·notebook 에 아무것도 쓰지 않는다 (RAG 담당 생성 평가용 → fix_internal)."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text 가 비어 있음")
    all_rules = golden.rules()
    if not all_rules:
        raise HTTPException(503, "rules.jsonl 이 없음 (data/golden/ 또는 _sample-B/)")
    unit_row = golden.find_unit(level, unit) or {}

    # 1) RAG 검색 → 상위 RAG_TOP_K 조각만 프롬프트에 (1위만 주면 검색이 틀린 문장을 놓침: 'I am hot lastyear' 에서 R-07 이 3위). 실패하면 규칙 전부 (폴백)
    cands, mode, fallback_reason = _search_candidates(text, k=RAG_TOP_K)
    prompt_rules = cands[:RAG_TOP_K] if mode == "rag" else all_rules
    allowed_ids = {r["id"] for r in prompt_rules}          # 모델이 고를 수 있는 규칙 = 실제로 전달한 것만

    prompt = _render(
        PROMPT_FILE.read_text(encoding="utf-8"),
        mission=unit_row.get("mission") or "(미션 없음 — 미션 확인은 ok=true 로)",
        hint_words=", ".join(unit_row.get("hint_words") or []) or "(없음)",
        all_rules=_rules_block(prompt_rules),
        sentence=text,
    )
    shown = [(c["id"], round(c["score"], 3)) for c in cands] if cands else [r["id"] for r in all_rules]
    print(f"[fix] student={student} unit={unit} mode={mode}{' (' + fallback_reason + ')' if fallback_reason else ''} candidates={shown} text={text!r}", flush=True)

    # 2) 생성 → 3) 검증. 검증에 걸리면 이유를 덧붙여 한 번 더 생성, 그래도 안 되면 502
    problem = None
    for attempt in (1, 2):
        sent = prompt if attempt == 1 else prompt + f"\n\n## 다시: 직전 답이 규칙 위반이었다 ({problem}). 4번 규칙대로 wrong 은 문장에 있는 단어 하나, fix 는 그 단어를 바꾼 것만 쓴다."
        if settings.log_prompt:                                  # 모델에 실제로 보내는 프롬프트 전문 (LOG_PROMPT=0 으로 끔)
            print(f"[fix] ── 프롬프트 ({attempt}차, {len(sent)}자, 규칙 {len(prompt_rules)}개) ──\n{sent}\n[fix] ── 프롬프트 끝 ──", flush=True)
        try:
            out = _ask_llm(sent)
        except llm.LLMError as e:                            # 할당량·네트워크·JSON 파싱
            raise HTTPException(502, str(e))
        llm_info = out.pop("_llm", {})
        print(f"[fix] {llm_info.get('backend')}:{llm_info.get('model')} {llm_info.get('ms')}ms 응답: {json.dumps(out, ensure_ascii=False)}", flush=True)

        ok = bool(out.get("ok"))
        rule_id = (out.get("rule_id") or "").strip() if not ok else ""
        if not ok and rule_id not in allowed_ids:            # 근거 밖 규칙 (전체 목록 기준이 아니라 '전달한 근거' 기준 — 인계문서 4번)
            problem = f"근거 밖 규칙 id={rule_id or '없음'} (전달한 근거: {sorted(allowed_ids)})"
        elif not ok:
            rt = (golden.find_rule(rule_id) or {}).get("type", "")
            problem = _pair_problem(text, out.get("wrong"), out.get("fix"), rt)
        else:
            problem = None
        if problem is None:
            break
        print(f"[fix] 검증 실패({attempt}차): {problem}", flush=True)
    if problem is not None:
        raise HTTPException(502, f"모델 답이 규칙에 안 맞아 버렸어요 ({problem}). 다시 [고쳐줘]를 눌러 주세요.")
    rule = golden.find_rule(rule_id) if not ok else None

    raw_fixed = (out.get("fixed") or text).strip()
    fixed = raw_fixed
    single = _single_fix(text, out.get("wrong"), out.get("fix")) if not ok else None
    norm = lambda x: re.sub(r"[.!?\s]+$", "", x).strip().lower()          # 끝 문장부호·대소문자 차이는 "여러 곳 고침" 으로 보지 않는다
    if single and norm(single) != norm(fixed):
        print(f"[fix] 모델이 여러 곳을 고침 → 1위 규칙만 반영: {fixed!r} → {single!r}", flush=True)
    if single:
        fixed = single                                       # 표기(첫 글자 대문자·마침표)는 항상 서버 기준으로 통일
    full_fixed = (out.get("full_fixed") or "").strip() or fixed
    if not ok and not _full_fixed_ok(text, full_fixed, out.get("fix")):   # 학생이 안 쓴 내용을 덧붙인 문장('to the zoo and …')은 버린다
        print(f"[fix] full_fixed 에 새 내용이 들어가 버림: {full_fixed!r} → {fixed!r}", flush=True)
        full_fixed = fixed
    log_id = "L-" + datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    mission = out.get("mission") if isinstance(out.get("mission"), dict) else {"ok": True, "nudge": ""}

    # 4) 근거·점수는 모델이 아니라 '서버가 전달한 후보' 에서 구성 (인계문서 2절)
    top = cands[0] if cands else None
    chosen = next((c for c in cands if rule and c["id"] == rule["id"]), None)          # 모델이 고른 규칙의 검색 후보
    second = next((c for c in cands if chosen and c["id"] != chosen["id"]), None)      # 그 외 후보 중 최고 점수
    if rule and mode == "rag" and chosen:
        rule_field = {"id": chosen["id"], "name": chosen["type"], "score": round(chosen["score"], 4), "rank": cands.index(chosen) + 1}
        source = {"chunk_id": chosen["id"], "text": chosen["text"]}
    elif rule:
        rule_field = {"id": rule["id"], "name": rule["type"], "score": None}
        source = {"chunk_id": rule["id"], "text": rule["text"]}
    else:
        rule_field, source = None, None
    runner_up = {"id": second["id"], "name": second["type"], "score": round(second["score"], 4)} if (rule and second and mode == "rag") else None   # ok 면 rule 과 함께 null

    result = {
        "ok": ok,
        "rule": rule_field,
        "runner_up": runner_up,
        "wrong": None if ok else out.get("wrong"),
        "fix": None if ok else out.get("fix"),
        "fixed": text if ok else fixed,
        "why": out.get("why") or ("문법에 맞는 문장이에요. 다른 문장도 말해볼까요?" if ok else ""),
        "source": source,
        "more_errors": bool(out.get("more_errors")) and not ok,
        "full_fixed": text if ok else full_fixed,              # 다 고친 문장 (2차 뒤에도 남았을 때 화면이 최종 정답으로 보여줌)
        "suggested_questions": [q for q in (out.get("suggested_questions") or []) if isinstance(q, str)][:2] + ["다른 예문 보여줘"],
        "mission": {"ok": bool(mission.get("ok", True)), "nudge": mission.get("nudge") or ""},
        "log_id": log_id,
        "mode": mode,
        "fallback_reason": fallback_reason,                    # "search_error" | "no_results" | None
        "candidates": [{"id": c["id"], "name": c["type"], "score": round(c["score"], 4)} for c in cands],   # 검색 상위 k (관리자·실험용)
        "llm": llm_info,                                       # {"backend","model","ms","fallback_from"} — 비교 실험·관리자용
    }

    if record:
        _log_sentence({
            "log_id": log_id, "ts": datetime.now().isoformat(timespec="seconds"), "student": student,
            "level": level, "unit": unit, "text": text, "source": source_kind,
            "rule_id": rule["id"] if rule else None, "ok": ok, "fixed": result["fixed"],
            "mission_ok": result["mission"]["ok"], "mode": mode, "fallback_reason": fallback_reason,
            "top_score": round(top["score"], 4) if top else None,
            "llm": llm_info.get("backend"), "llm_ms": llm_info.get("ms"),
        })
        if rule:
            _notebook_add(student, rule["id"], log_id)
    print(f"[fix] 결과: ok={ok} rule={rule['id'] if rule else None} mode={mode} fixed={result['fixed']!r} more_errors={result['more_errors']} "
          f"mission_ok={result['mission']['ok']} log_id={log_id}{'' if record else ' (기록 안 함)'}", flush=True)
    return result


def fix_internal(text: str, level: int = 2, unit: str = "") -> dict:
    """POST /fix 와 같은 로직이되 sentence_log·notebook 에 기록하지 않는다. 반환 형식은 /fix 응답과 동일.
    RAG 담당의 생성 평가(tests/eval_rag.py --with-generation)용 (인계문서 6번). HTTPException 은 그대로 올라간다."""
    return diagnose(text, level=level, unit=unit, student="EVAL", source_kind="eval", record=False)


@router.post("/fix")
def fix(body: FixIn):
    if not settings.has_api_key and (settings.llm_backend or "gemini") == "gemini":
        raise HTTPException(500, "GEMINI_API_KEY 가 설정되어 있지 않음")
    return diagnose(body.text, level=body.level, unit=body.unit, student=body.student, source_kind=body.source, record=True)
