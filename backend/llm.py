"""
LLM 제공자 스위치 — Gemini(기본) 또는 선생님 서버의 로컬 모델 (Ollama / vLLM)   구조·호출부: 팀장 · 로컬 쪽 구현·운영: TTS 팀원

호출하는 쪽(tutor.py /fix, ask.py /ask)은 이 함수 하나만 쓴다:
    from backend import llm
    out = llm.generate_json(prompt)          # dict 로 파싱된 JSON + 어느 백엔드가 답했는지

설정 (.env):
    LLM_BACKEND=gemini | local              기본 gemini. local 이면 선생님 서버의 OpenAI 호환 API 를 부른다
    LLM_LOCAL_URL=http://<선생님서버>:11434/v1   Ollama 는 /v1, vLLM 은 /v1 (둘 다 OpenAI 호환 chat/completions)
    LLM_LOCAL_MODEL=qwen2.5:7b-instruct     Ollama 태그 또는 vLLM 모델명
    LLM_LOCAL_API_KEY=                      vLLM 에 키를 걸었으면. Ollama 는 비워 둠
    LLM_TIMEOUT=30                          초. 로컬이 이보다 느리면 실패 처리
    LLM_FALLBACK=1                          local 이 실패하면 gemini 로 자동 대체 (0 이면 그대로 오류)

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
# 백엔드 2: 로컬 (OpenAI 호환 chat/completions — Ollama·vLLM 공통)   ← TTS 팀원 담당 구간
# ─────────────────────────────────────────────
def _local(prompt: str, timeout: float) -> str:
    if not settings.llm_local_url:
        raise LLMError("LLM_LOCAL_URL 이 비어 있음")
    url = settings.llm_local_url.rstrip("/") + "/chat/completions"
    body = {
        "model": settings.llm_local_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},   # Ollama ≥0.5 · vLLM 지원. 미지원 모델이면 프롬프트의 "JSON 만" 지시에 기댄다
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if settings.llm_local_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_local_api_key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"로컬 LLM HTTP {e.code}: {e.read()[:200]!r}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"로컬 LLM 연결 실패 ({url}): {e}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"로컬 LLM 응답 형식이 다름: {str(data)[:200]}") from e


_BACKENDS = {"gemini": _gemini, "local": _local}


# ─────────────────────────────────────────────
# 입구
# ─────────────────────────────────────────────
def generate_json(prompt: str, backend: str | None = None, timeout: float | None = None) -> dict:
    """프롬프트 → JSON dict. 결과 dict 에 `_llm` = {"backend", "model", "ms", "fallback_from"} 를 붙여 준다 (실험·로그용).
    backend 를 안 주면 .env 의 LLM_BACKEND. local 실패 + LLM_FALLBACK=1 이면 gemini 로 한 번 더."""
    name = (backend or settings.llm_backend or "gemini").lower()
    if name not in _BACKENDS:
        raise LLMError(f"모르는 LLM_BACKEND: {name} (gemini | local)")
    timeout = timeout or settings.llm_timeout

    t0 = time.time()
    try:
        text = _BACKENDS[name](prompt, timeout)
        out = _parse_json(text)
        out["_llm"] = {"backend": name, "model": settings.llm_local_model if name == "local" else settings.gemini_model,
                       "ms": int((time.time() - t0) * 1000), "fallback_from": None}
        return out
    except LLMError as e:
        if name == "local" and settings.llm_fallback:
            print(f"[llm] local 실패 → gemini 대체: {e}", flush=True)
            out = generate_json(prompt, backend="gemini", timeout=timeout)
            out["_llm"]["fallback_from"] = "local"
            return out
        raise


def generate_text(prompt: str, backend: str | None = None, timeout: float | None = None) -> str:
    """프롬프트 → 순수 텍스트 한 줄. generate_json 과 같은 백엔드 스위치·폴백을 쓰지만 JSON 파싱은 안 한다
    (STT 병합처럼 "문장 하나만 출력해" 같은 자유 텍스트 응답에 쓴다)."""
    name = (backend or settings.llm_backend or "gemini").lower()
    if name not in _BACKENDS:
        raise LLMError(f"모르는 LLM_BACKEND: {name} (gemini | local)")
    timeout = timeout or settings.llm_timeout

    try:
        return _BACKENDS[name](prompt, timeout).strip()
    except LLMError as e:
        if name == "local" and settings.llm_fallback:
            print(f"[llm] local 실패 → gemini 대체: {e}", flush=True)
            return generate_text(prompt, backend="gemini", timeout=timeout)
        raise
