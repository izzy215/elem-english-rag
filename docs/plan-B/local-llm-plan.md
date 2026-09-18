# 로컬 LLM (선생님 GPU 서버) 연동 — 작업 계획

작성 2026-09-08 · 팀장 · 담당: **TTS 팀원** (서버 설치·운영·검증) · 팀장 (호출부 `backend/llm.py`, 비교 실험) · 상태: 착수 전

## 0. 현재 운영 설정 (2026-09-08 결정)

| 항목 | 값 | 이유 |
|---|---|---|
| 서비스 기본 백엔드 | `LLM_BACKEND=local` (강의실 서버 Ollama qwen2.5:32b-instruct, 엔드포인트 이름 merge32b/local) | Gemini 무료 한도 회피. 비교 실험에서 Qwen 32b 가 로컬 중 최고. (초기엔 groq 임시 사용) |
| 실패 시 대체 | `LLM_FALLBACK=1` → gemini | 한도·연결·JSON 오류 때 그 요청만 Gemini 로. 콘솔 `[llm] local 실패 → gemini 대체` |
| 이름 바꿀 때 | `LLM_BACKEND=<이름>` | 한 줄 교체. 이름은 `.env` 의 `LLM_ENDPOINTS` 에 등록된 것만 (LLM_<NAME>_URL/KEY/MODEL) |
| 비교 실험 | `python -m tests.eval_fix --backend gemini,claude,local` (이름은 `.env` `LLM_ENDPOINTS` 에 있어야 함) | 결과 `data/rag_eval/fix_compare_<시각>[_label].json/.md` + `fix_compare_latest.*` 복사본 |

## 1. 목표와 비목표

**목표**
1. Gemini 한도(무료 등급 하루 20회)·장애 때 `/fix`(나중엔 `/ask`)가 강의실 서버의 로컬 모델로 **자동 대체**되어 서비스가 멈추지 않는다.
2. "같은 규칙 조각을 근거로 주면 소형 모델도 맞게 고치나?"를 **숫자로** 보여 준다 (발표 한 장). RAG를 "지식 확장이 아니라 근거 보증"으로 정의한 우리 기획의 증명.

**비목표** (이번엔 하지 않음)
- Gemini를 로컬로 **대체**하기. 주 경로는 Gemini 그대로. 로컬은 대체·실험용.
- 파인튜닝, 모델 비교 여러 개, 임베딩 로컬화(→ RAG 담당 별도), TTS 로컬화.

## 2. 구조 — 이미 만들어 둔 것

```
tutor.py /fix ─┐                       .env: LLM_BACKEND=gemini | local
ask.py   /ask ─┴─▶ backend/llm.py ─┬─ gemini  (지금 쓰는 것, 그대로)
                   generate_json()  ├─ claude  (Anthropic API · 비교 실험용, ANTHROPIC_API_KEY 필요, 무료 등급 없음)
                                    └─ <이름>  ──HTTP──▶ OpenAI 호환 엔드포인트 (이름 여러 개 등록: LLM_ENDPOINTS=teacher,groq,…)
                                        │             ├─ teacher: 강의실 서버 Ollama/vLLM  qwen2.5:7b-instruct 등
                                        │             └─ groq / mistral / openrouter …: 무료 티어 있는 공개 모델 API
                                        └─ gemini 아닌 백엔드 실패 시 gemini 로 폴백 (LLM_FALLBACK=1)
```

- 호출부는 백엔드를 모른다. `.env` 한 줄로 바꾼다. 응답에 `llm: {backend, model, ms, fallback_from}`이 붙고 sentence_log에도 기록되므로 어느 모델이 답했는지 나중에 셀 수 있다.
- `backend/llm.py`의 `_openai_compat(name, prompt, timeout)`은 OpenAI 호환 API를 부르는 코드까지 들어 있다 (이름별 URL·KEY·MODEL 은 `.env`). **TTS 팀원이 할 일은 "그 API가 강의실 서버에 떠 있게 하는 것"과 "우리 프롬프트로 JSON이 제대로 나오는지 확인"이다.**

## 3. 작업 순서와 완료 기준

### 작업 1. 강의실 서버 확인 (TTS 팀원)
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
`.env`에 네 줄 추가 후 파이참 서버 재시작 (`teacher` 라는 이름으로 등록. Groq 등 다른 OpenAI 호환 API 도 같은 방식으로 이름만 늘리면 됨):
```
LLM_ENDPOINTS=teacher
LLM_TEACHER_URL=http://<서버IP>:11434/v1
LLM_TEACHER_MODEL=qwen2.5:7b-instruct
LLM_BACKEND=teacher
```
- [x] 튜터 화면에서 "I go to the zoo yesterday."로 [고쳐줘] → 콘솔 `[fix] local:qwen2.5:14b-instruct 12690ms 응답: {...}` 확인 (2026-09-09, /api/fix 직접 호출로 검증. 모델은 계획 당시 후보였던 7b 대신 서버 VRAM 여유로 14b·32b 등 사용. 엔드포인트 이름은 검증 당시 `LLM_LOCAL_*`(자동으로 "local" 등록)이었고, 팀 표준인 `LLM_ENDPOINTS=teacher`로 이름만 바꿔도 동작은 동일)
- [x] 서버를 끈 상태로 다시 → 콘솔 `[llm] local 실패 → gemini 대체` 가 찍히고 화면은 정상 진단 (폴백 동작) (2026-09-09, URL을 존재하지 않는 포트로 바꿔 연결 실패를 재현·확인. 새 llm.py 는 `name != "gemini"`면 전부 폴백 대상이라 teacher 로 이름을 바꿔도 그대로 동작)
- [x] `LLM_BACKEND=gemini`(또는 groq)로 되돌려 두기 (주 경로) — 완료

완료 기준: 위 세 가지 캡처. `/fix` 응답의 `llm.backend`가 각각 local(→teacher) / gemini(fallback_from) / gemini. → **모두 확인됨.**
참고: 강의실 서버 접속은 SSH 터널(`ssh -L 11434:localhost:11434 research1@192.168.1.147`) 또는 같은 네트워크면 서버 IP로 직접 접속 가능(`http://192.168.1.147:11434`, OLLAMA_HOST=0.0.0.0). VSCode 자동 포트 포워딩·죽지 않은 옛 ssh 세션이 겹치면 응답이 안 오는 문제가 있었음(새로 깨끗하게 띄우면 해결). Ollama 는 `nohup ... &`로 띄워서 VSCode/SSH 세션을 닫아도 서버 재부팅 전까지 계속 돎.

### 작업 4. 비교 실험 (팀장 + TTS 팀원)
`tests/eval_fix.py` (만들어 둠, `--backend gemini,claude,<엔드포인트 이름>` 또는 `all` — 이름은 `.env` `LLM_ENDPOINTS` 에 등록된 것): 기본은 **실제 파이프라인 전체**(`tutor.fix_internal`, 검색 상위 5 + Unit·공통 규칙 + 검증·철자·규칙 밖 처리, fallback=False)로 eval.csv **72문장 전부**를 백엔드별로 돌려 표로 만든다. `--limit n` 으로 앞 n 문장만, `--no-rag` 는 검색 없이 규칙 전부를 넣는 기준선, `--label` 은 실행 이름(파일명·표 제목).

| 문장 | 정답 규칙 | Gemini | Claude | 강의실 서버 7B | Groq 70B (무료) |
|---|---|---|---|---|---|

- [ ] 규칙 적중(rule_id 일치), 고친 문장 일치, 정상 문장 2개 오교정 여부, 평균 응답 시간
- [ ] 모델 1개 더(후보 2) 돌려 보면 발표 표가 풍성해짐 (선택)
- [x] 결과는 `data/rag_eval/fix_compare_<시각>[_label].json/.md` + `fix_compare_latest.*` 복사본에 저장 (git 제외). json 에 색인 정보(임베딩 모델 · 규칙 수 · 생성 시각)도 같이 기록. 표는 발표 자료로

완료 기준: 10문장 × 2모델 표 하나. "근거 조각을 주면 7B도 n/10" 문장 하나.

### 작업 5. `/ask`도 같은 스위치 쓰기 (TTS 팀원, 선택)
ask.py가 Gemini를 직접 부르는 부분을 `llm.generate_json(prompt)`로 바꾸면 `/ask`도 자동으로 대체·실험 대상이 된다.

## 4. 점검표 (파일 기준)

| 파일 | 담당 | 상태 |
|---|---|---|
| backend/llm.py | 팀장 | ✅ 완료 (gemini · claude · `LLM_ENDPOINTS` 의 OpenAI 호환 엔드포인트 이름별 호출, gemini 아닌 백엔드 실패 시 폴백, `LLM_TIMEOUT`) |
| backend/config.py `LLM_*` | 팀장 | ✅ |
| backend/tutor.py → llm 사용 | 팀장 | ✅ 응답·로그에 llm 정보 |
| .env.example `LLM_*` | 팀장 | ✅ |
| 강의실 서버 Ollama + 모델 | TTS 팀원 | ✅ qwen2.5(7b/14b/32b-instruct), gemma2:9b, exaone3.5:7.8b, mistral:7b 받아둠 |
| 연결 검증 3종 캡처 | TTS 팀원 | ✅ 작업 3 완료 |
| tests/eval_fix.py + 비교표 | 팀장 (+TTS 팀원 실행) | ✅ 10문장 기준 qwen2.5:32b 9/10, 14b/7b 7/10, exaone 6/10, gemma2 2/10, mistral 3/10 (Gemini 10/10). "Qwen 계열이 다른 가문보다 크게 앞섬"이 발표 포인트 |
| ask.py → llm 사용 | TTS 팀원 | ✅ 응답에 llm 정보, 로컬 매칭 우회 시(문장 정오 판정 포함) 전부 llm.py 경유 |

## 5. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 로컬 모델이 JSON 형식을 안 지킴 | `response_format=json_object` + 프롬프트 "JSON만" 이중. 그래도 깨지면 llm.py가 LLMError → Gemini 폴백. 실험표엔 "형식 실패"로 집계 |
| 로컬이 느림 (7B 가 문장당 3~10초) | `LLM_TIMEOUT=30`. 대체 경로라 허용. 실험표에 ms 기록 |
| 강의실 서버가 학교 밖에서 안 닿음 | 시연 장소가 학교면 문제 없음. 밖이면 Gemini 주 경로로 시연하고 로컬은 비교표로만 |
| 8GB VRAM 에 7B 가 안 올라감 | q4 양자화 태그 사용, 안 되면 3B(qwen2.5:3b) 로 낮춤. 실험 목적엔 충분 |
| 로컬 결과가 나쁨 | 그것도 결과. "근거를 줘도 7B는 5/10, Gemini는 9/10" 역시 발표 문장이 됨 |

## 6. 선생님께 여쭤볼 것 (작업 1)

1. 서버 IP와 SSH 계정, 팀원 PC에서 11434 포트로 접속 가능한지
2. GPU 메모리(5060이 8GB인지 16GB인지)와 CUDA 설치 여부
3. Ollama(또는 Docker) 설치 허용 여부, 디스크 여유(모델 1개당 4~6GB)

## 7. 강의실 서버 Ollama 운영 참고 (2026-09-18)

강의실 서버는 GPU 2장(whisper_server.py가 GPU0 점유)을 여러 팀이 공유한다. Ollama를
기본값으로 띄우면 GPU0 여유 공간이 부족해 32B 모델이 거의 CPU로 밀려나(`size_vram`이
전체 크기의 1% 수준) `LLM_TIMEOUT=60`을 넘겨 실패한다. 반드시 아래 3개 환경변수를
지정해서 띄워야 한다(`nohup ollama serve`만 치면 재발함):

```bash
CUDA_VISIBLE_DEVICES=1 \
OLLAMA_MODELS=/home/research1/workspace/team2/elem-english-rag/ollama-models \
OLLAMA_HOST=0.0.0.0:11434 \
nohup /home/research1/ollama/bin/ollama serve > ollama.log 2>&1 &
```

- `CUDA_VISIBLE_DEVICES=1`: whisper_server.py가 쓰는 GPU0을 피해 GPU1에 전부 올린다.
- `OLLAMA_MODELS`: 기본 경로(`~/.ollama/models`)가 아니라 실제 모델이 있는 경로.
- `OLLAMA_HOST=0.0.0.0:11434`: 안 주면 `127.0.0.1`로만 바인딩돼 팀원 PC에서 접속 불가.

서버 재부팅/재시작마다 잊기 쉬우니, 가능하면 systemd 서비스로 등록해서 위 세 환경변수를
고정해두는 걸 권장.
