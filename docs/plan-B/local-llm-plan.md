# 로컬 LLM (선생님 GPU 서버) 연동 — 작업 계획

작성 2026-09-08 · 팀장 · 담당: **TTS 팀원** (서버 설치·운영·검증) · 팀장 (호출부 `backend/llm.py`, 비교 실험) · 상태: 착수 전

## 1. 목표와 비목표

**목표**
1. Gemini 한도(무료 등급 하루 20회)·장애 때 `/fix`(나중엔 `/ask`)가 선생님 서버의 로컬 모델로 **자동 대체**되어 서비스가 멈추지 않는다.
2. "같은 규칙 조각을 근거로 주면 소형 모델도 맞게 고치나?"를 **숫자로** 보여 준다 (발표 한 장). RAG를 "지식 확장이 아니라 근거 보증"으로 정의한 우리 기획의 증명.

**비목표** (이번엔 하지 않음)
- Gemini를 로컬로 **대체**하기. 주 경로는 Gemini 그대로. 로컬은 대체·실험용.
- 파인튜닝, 모델 비교 여러 개, 임베딩 로컬화(→ RAG 담당 별도), TTS 로컬화.

## 2. 구조 — 이미 만들어 둔 것

```
tutor.py /fix ─┐                       .env: LLM_BACKEND=gemini | local
ask.py   /ask ─┴─▶ backend/llm.py ─┬─ gemini  (지금 쓰는 것, 그대로)
                   generate_json()  └─ local   ──HTTP──▶ 선생님 서버  Ollama(또는 vLLM)  OpenAI 호환 /v1/chat/completions
                                        │                                └─ qwen2.5:7b-instruct 등
                                        └─ local 실패 시 gemini 로 폴백 (LLM_FALLBACK=1)
```

- 호출부는 백엔드를 모른다. `.env` 한 줄로 바꾼다. 응답에 `llm: {backend, model, ms, fallback_from}`이 붙고 sentence_log에도 기록되므로 어느 모델이 답했는지 나중에 셀 수 있다.
- `backend/llm.py`의 `_local()`은 OpenAI 호환 API를 부르는 코드까지 들어 있다. **TTS 팀원이 할 일은 "그 API가 선생님 서버에 떠 있게 하는 것"과 "우리 프롬프트로 JSON이 제대로 나오는지 확인"이다.**

## 3. 작업 순서와 완료 기준

### 작업 1. 선생님 서버 확인 (TTS 팀원)
- [ ] 접속 방식: SSH 계정 / 팀원 PC에서 HTTP로 닿는 IP·포트 (방화벽에 11434 또는 8001 열기)
- [ ] OS, NVIDIA 드라이버, `nvidia-smi`로 5060 ×2 인식·VRAM 크기 (8GB인지 16GB인지)
- [ ] Docker 또는 직접 설치 가능 여부

완료 기준: 팀원 PC에서 `curl http://<서버IP>:11434/` 가 응답한다.

### 작업 2. Ollama 설치 + 모델 1개 (TTS 팀원)
```bash
# 서버에서
curl -fsSL https://ollama.com/install.sh | sh
OLLAMA_HOST=0.0.0.0 ollama serve          # 외부 접속 허용
ollama pull qwen2.5:7b-instruct           # 후보 1 (한국어 설명 무난, 7B, 8GB VRAM 에 4bit 로 들어감)
# 후보 2: gemma2:9b-instruct   후보 3: exaone3.5:7.8b (한국어 강함)
```
- [ ] VRAM이 8GB×2라면 7B 4bit(q4_K_M) 기준. 두 장을 한 모델에 합쳐 쓰는 건 Ollama가 자동으로 나눠 올린다.
- [ ] 우리 프롬프트 파일 `backend/prompts/fix_fallback.txt`에 규칙 8개·문장 하나를 손으로 채워 서버에서 직접 던져 본다:
```bash
curl http://<서버IP>:11434/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"qwen2.5:7b-instruct","messages":[{"role":"user","content":"<프롬프트 전문>"}],"response_format":{"type":"json_object"},"temperature":0.2}'
```

완료 기준: 위 curl이 `{"ok":false,"rule_id":"R-01",...}` 모양의 **JSON만** 돌려준다 (앞뒤 설명 없이). 응답 시간 기록.

### 작업 3. 우리 서버에서 연결 (TTS 팀원 → 팀장 확인)
`.env`에 세 줄 추가 후 파이참 서버 재시작:
```
LLM_BACKEND=local
LLM_LOCAL_URL=http://<서버IP>:11434/v1
LLM_LOCAL_MODEL=qwen2.5:7b-instruct
```
- [ ] 튜터 화면에서 "I go to the zoo yesterday."로 [고쳐줘] → 파이참 콘솔 `[fix] local:qwen2.5:7b-instruct 1234ms 응답: {...}` 확인
- [ ] 서버를 끈 상태로 다시 → 콘솔 `[llm] local 실패 → gemini 대체` 가 찍히고 화면은 정상 진단 (폴백 동작)
- [ ] `LLM_BACKEND=gemini`로 되돌려 두기 (주 경로)

완료 기준: 위 세 가지 캡처. `/fix` 응답의 `llm.backend`가 각각 local / gemini(fallback_from: local) / gemini.

### 작업 4. 비교 실험 (팀장 + TTS 팀원)
`tests/eval_fix.py` (팀장이 만듦): eval.csv 10문장을 **같은 프롬프트·같은 규칙 조각**으로 Gemini와 로컬에 각각 보내 표로 만든다.

| 문장 | 정답 규칙 | Gemini 규칙 / 고침 / ms | 로컬 규칙 / 고침 / ms |
|---|---|---|---|

- [ ] 규칙 적중(rule_id 일치), 고친 문장 일치, 정상 문장 2개 오교정 여부, 평균 응답 시간
- [ ] 모델 1개 더(후보 2) 돌려 보면 발표 표가 풍성해짐 (선택)
- [ ] 결과는 `data/rag_eval/fix_compare.json`에 저장 (git 제외), 표는 발표 자료로

완료 기준: 10문장 × 2모델 표 하나. "근거 조각을 주면 7B도 n/10" 문장 하나.

### 작업 5. `/ask`도 같은 스위치 쓰기 (TTS 팀원, 선택)
ask.py가 Gemini를 직접 부르는 부분을 `llm.generate_json(prompt)`로 바꾸면 `/ask`도 자동으로 대체·실험 대상이 된다.

## 4. 점검표 (파일 기준)

| 파일 | 담당 | 상태 |
|---|---|---|
| backend/llm.py | 팀장 | ✅ 뼈대 완료 (gemini 구현, local 호출 코드 포함, 폴백) |
| backend/config.py `LLM_*` | 팀장 | ✅ |
| backend/tutor.py → llm 사용 | 팀장 | ✅ 응답·로그에 llm 정보 |
| .env.example `LLM_*` | 팀장 | ✅ |
| 선생님 서버 Ollama + 모델 | TTS 팀원 | ⬜ 작업 1~2 |
| 연결 검증 3종 캡처 | TTS 팀원 | ⬜ 작업 3 |
| tests/eval_fix.py + 비교표 | 팀장 (+TTS 팀원 실행) | ⬜ 작업 4 |
| ask.py → llm 사용 | TTS 팀원 | ⬜ 작업 5 (선택) |

## 5. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 로컬 모델이 JSON 형식을 안 지킴 | `response_format=json_object` + 프롬프트 "JSON만" 이중. 그래도 깨지면 llm.py가 LLMError → Gemini 폴백. 실험표엔 "형식 실패"로 집계 |
| 로컬이 느림 (7B 가 문장당 3~10초) | `LLM_TIMEOUT=30`. 대체 경로라 허용. 실험표에 ms 기록 |
| 선생님 서버가 학교 밖에서 안 닿음 | 시연 장소가 학교면 문제 없음. 밖이면 Gemini 주 경로로 시연하고 로컬은 비교표로만 |
| 8GB VRAM 에 7B 가 안 올라감 | q4 양자화 태그 사용, 안 되면 3B(qwen2.5:3b) 로 낮춤. 실험 목적엔 충분 |
| 로컬 결과가 나쁨 | 그것도 결과. "근거를 줘도 7B는 5/10, Gemini는 9/10" 역시 발표 문장이 됨 |

## 6. 선생님께 여쭤볼 것 (작업 1)

1. 서버 IP와 SSH 계정, 팀원 PC에서 11434 포트로 접속 가능한지
2. GPU 메모리(5060이 8GB인지 16GB인지)와 CUDA 설치 여부
3. Ollama(또는 Docker) 설치 허용 여부, 디스크 여유(모델 1개당 4~6GB)
