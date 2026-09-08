"""
LLM 제공자 스위치 — Gemini(기본) · Claude(Anthropic API) · 선생님 서버의 로컬 모델 (Ollama / vLLM)   구조·호출부: 팀장 · 로컬 쪽 구현·운영: TTS 팀원

호출하는 쪽(tutor.py /fix, ask.py /ask)은 이 함수 하나만 쓴다:
    from backend import llm
    out = llm.generate_json(prompt)          # dict 로 파싱된 JSON + 어느 백엔드가 답했는지

설정 (.env):
    LLM_BACKEND=gemini | claude | <엔드포인트 이름>   서비스가 쓸 기본 백엔드. 기본 gemini
    ANTHROPIC_API_KEY=sk-ant-...            claude 백엔드 키 (console.anthropic.com). 무료 등급 없음 — 선불 크레딧
    LLM_CLAUDE_MODEL=claude-opus-5          Claude 모델 id
    LLM_ENDPOINTS=groq,teacher              OpenAI 호환 엔드포인트 이름 목록 (원하는 만큼). 이름마다 아래 세 줄
    LLM_GROQ_URL=https://api.groq.com/openai/v1   LLM_GROQ_KEY=gsk_...   LLM_GROQ_MODEL=llama-3.3-70b-versatile
    LLM_TEACHER_URL=http://<선생님서버>:11434/v1   (Ollama 는 키 없음)   LLM_TEACHER_MODEL=qwen2.5:7b-instruct
    LLM_LOCAL_URL / _MODEL / _API_KEY       예전 설정. 있으면 'local' 이름으로 자동 등록
    LLM_TIMEOUT=30                          초. 로컬이 이보다 느리면 실패 처리
    LLM_FALLBACK=1                          gemini 가 아닌 백엔드가 실패하면 gemini 로 자동 대체 (0 이면 그대로 오류)

왜 이렇게 나누나:
  - 서비스 주 경로는 Gemini 그대로. 로컬은 (1) Gemini 한도·장애 때 대체, (2) "같은 규칙 조각을 주면 소형 모델도 맞게 고치나" 비교 실험용.
  - 호출부는 백엔드를 모른다. 바꾸는 건 .env 한 줄.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from backend.config import settings

_client = None   # Gemini 클라이언트 (한 번만 생성)


class LLMError(RuntimeError):
    """백엔드 호출 실패 (네트워크·한도·JSON 파싱)."""


# ─────────────────────────────────────────────
# 공통
# ─────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON 파싱 실패: {e} · 앞 120자: {text[:120]!r}") from e


# ─────────────────────────────────────────────
# 백엔드 1: Gemini (지금 쓰는 것)
# ─────────────────────────────────────────────
def _gemini(prompt: str, timeout: float) -> str:
    global _client
    from google import genai
    from google.genai import types
    if not settings.has_api_key:
        raise LLMError("GEMINI_API_KEY 가 설정되어 있지 않음")
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    try:
        resp = _client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
    except Exception as e:                       # 429 한도, 네트워크 등
        raise LLMError(f"Gemini 호출 실패: {e}") from e
    return resp.text or ""


# ─────────────────────────────────────────────
# 백엔드 2: OpenAI 호환 엔드포인트 (이름 여러 개) — 선생님 서버 Ollama/vLLM, Groq, Mistral, OpenRouter, Cerebras … 전부 같은 규격
#   .env: LLM_ENDPOINTS=groq,teacher  +  LLM_GROQ_URL / LLM_GROQ_KEY / LLM_GROQ_MODEL, LLM_TEACHER_URL / LLM_TEACHER_MODEL …
#   예전 LLM_LOCAL_* 은 'local' 이름으로 자동 등록
# ─────────────────────────────────────────────
def _openai_compat(name: str, prompt: str, timeout: float) -> str:
    ep = (settings.llm_endpoints or {}).get(name)
    if not ep or not ep.get("url"):
        raise LLMError(f"엔드포인트 '{name}' 설정 없음 (.env 의 LLM_ENDPOINTS 와 LLM_{name.upper()}_URL 확인)")
    url = ep["url"].rstrip("/") + "/chat/completions"
    body = {
        "model": ep.get("model") or "",
        "messages": [{"role": "system", "content": "너는 JSON 만 출력한다. 설명·코드펜스 없이 JSON 객체 하나만 답한다."},
                     {"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},   # Ollama ≥0.5 · vLLM · Groq · OpenRouter 지원. 미지원이면 위 system 지시에 기댄다
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "User-Agent": "elem-english-rag/0.1 (+FastAPI)"}   # 파이썬 기본 UA 는 Groq 앞단 Cloudflare 가 403(1010) 으로 막음
    if ep.get("key"):
        headers["Authorization"] = f"Bearer {ep['key']}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"{name} HTTP {e.code}: {e.read()[:200]!r}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"{name} 연결 실패 ({url}): {e}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"{name} 응답 형식이 다름: {str(data)[:200]}") from e


# ─────────────────────────────────────────────
# 백엔드 3: Claude (Anthropic 공식 SDK)   ← 비교 실험용. 무료 등급이 없어 콘솔에서 크레딧을 넣어야 한다
# ─────────────────────────────────────────────
_claude_client = None


def _claude(prompt: str, timeout: float) -> str:
    global _claude_client
    import anthropic
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY 가 설정되어 있지 않음")
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=timeout, max_retries=1)
    kwargs = {}
    if not settings.claude_model.startswith("claude-haiku"):   # effort 는 Opus/Sonnet 5 계열만 지원. Haiku 4.5 는 넣으면 400
        kwargs["output_config"] = {"effort": "low"}             # 단답 교정 작업이라 낮은 effort 로 충분 (adaptive thinking 은 켜 둔 채)
    try:
        resp = _claude_client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system="너는 JSON 만 출력한다. 설명·코드펜스 없이 JSON 객체 하나만 답한다.",
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
    except anthropic.RateLimitError as e:
        raise LLMError(f"Claude 한도 초과(429): {e.message}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude HTTP {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"Claude 연결 실패: {e}") from e
    if resp.stop_reason == "refusal":
        raise LLMError("Claude 가 응답을 거절함 (refusal)")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


_BUILTIN = {"gemini": _gemini, "claude": _claude}


def backends() -> list[str]:
    """지금 설정으로 부를 수 있는 백엔드 이름 전부 (내장 2 + .env 에 등록한 OpenAI 호환 엔드포인트)."""
    return list(_BUILTIN) + list((settings.llm_endpoints or {}).keys())


def _model_of(name: str) -> str:
    if name == "gemini":
        return settings.gemini_model
    if name == "claude":
        return settings.claude_model
    return (settings.llm_endpoints or {}).get(name, {}).get("model", "")


# ─────────────────────────────────────────────
# 입구
# ─────────────────────────────────────────────
def generate_json(prompt: str, backend: str | None = None, timeout: float | None = None, fallback: bool | None = None) -> dict:
    """프롬프트 → JSON dict. 결과 dict 에 `_llm` = {"backend", "model", "ms", "fallback_from"} 를 붙여 준다 (실험·로그용).
    backend 를 안 주면 .env 의 LLM_BACKEND. gemini 아닌 백엔드가 실패하고 fallback(기본 .env 의 LLM_FALLBACK)이 켜져 있으면 gemini 로 한 번 더.
    비교 실험처럼 대체가 있으면 안 되는 곳은 fallback=False 로 부른다."""
    name = (backend or settings.llm_backend or "gemini").lower()
    if name not in backends():
        raise LLMError(f"모르는 LLM_BACKEND: {name} (가능: {', '.join(backends())})")
    timeout = timeout or settings.llm_timeout

    t0 = time.time()
    try:
        text = _BUILTIN[name](prompt, timeout) if name in _BUILTIN else _openai_compat(name, prompt, timeout)
        out = _parse_json(text)
        out["_llm"] = {"backend": name, "model": _model_of(name),
                       "ms": int((time.time() - t0) * 1000), "fallback_from": None}
        return out
    except LLMError as e:
        use_fallback = settings.llm_fallback if fallback is None else fallback
        if name != "gemini" and use_fallback:
            print(f"[llm] {name} 실패 → gemini 대체: {e}", flush=True)
            out = generate_json(prompt, backend="gemini", timeout=timeout)
            out["_llm"]["fallback_from"] = name
            return out
        raise
