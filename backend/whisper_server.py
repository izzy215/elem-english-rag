"""GPU 서버에서 Whisper STT를 API로 서빙하는 최소 스크립트 (Ollama 처럼 별도 프로세스로 nohup 실행).
이 프로젝트 앱(backend/speak.py)이 임포트하는 파일이 아니다 — 서버에 이 파일 하나만 올려서 독립 실행한다.

서버에서 실행 (예: ~/workspace/.venv 처럼 torch+CUDA 있는 가상환경 활성화 후):
    pip install fastapi uvicorn
    nohup python whisper_server.py > whisper_server.log 2>&1 &

speak.py 쪽에서 쓰려면 .env 에 WHISPER_SERVER_URL=http://<서버IP>:8001 추가.
없으면(기본) speak.py 는 이 서버를 몰라도 되고, 그냥 로컬 Whisper를 그대로 쓴다.
"""
import base64
import os
import tempfile

import uvicorn
import whisper
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
_models: dict[str, "whisper.Whisper"] = {}   # 모델 이름별 캐시 — 여러 개 요청해도 한 번만 로드
# GPU는 WHISPER_SERVER_DEVICE로 고른다(기본 cuda:0, embed_server.py의 EMBED_SERVER_DEVICE와 같은
# 패턴) — 이 서버는 team1/다른 실험과 같은 장비를 공유해서, GPU 0이 이미 꽉 차 있으면(다른 팀
# 프로세스가 10GiB+ 점유) large-v3 로드가 CUDA OOM으로 실패한다(2026-09-16 재현 — whisper_server.log에
# "CUDA out of memory... GPU 0 has ... of which 9.38 MiB is free" 확인). `nvidia-smi`로 여유 있는
# GPU 번호를 확인해 WHISPER_SERVER_DEVICE=cuda:1 처럼 지정하고 재시작.
DEVICE = os.environ.get("WHISPER_SERVER_DEVICE", "cuda:0")


def _get_model(name: str):
    if name not in _models:
        _models[name] = whisper.load_model(name, device=DEVICE)
    return _models[name]


class TranscribeIn(BaseModel):
    audio_base64: str
    mime: str = "audio/webm"
    language: str | None = None
    model: str = "large-v3"
    # True면 아래 언어 자동판정·덮어쓰기를 끄고 language 를 그대로 강제한다 — speak.py의 hybrid_stt()가
    # "한국어로 강제/영어로 강제" 두 번을 일부러 다르게 시켜서 비교하는 용도라, 자동판정이 둘을 같은
    # 값으로 덮어써버리면 비교 자체가 무의미해짐(2026-09-17, TTS 담당 요청 — 감지 확신 높은 오디오는
    # language='ko'/'en' 요청이 완전히 같은 텍스트로 돌아오는 게 실측 확인됨).
    force: bool = False


@app.post("/transcribe")
def transcribe(body: TranscribeIn):
    ext = ".wav" if "wav" in body.mime else ".webm" if "webm" in body.mime else ".mp3" if "mp3" in body.mime else ".mp4"
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(base64.b64decode(body.audio_base64))
            path = f.name
        model = _get_model(body.model)

        if body.force:
            language = body.language
            detected = prob = None
        else:
            # 1) 언어 감지 (앞 30초, GPU 0.1초). 화면이 'en' 이라고 보내도 실제 한국어면 Whisper 가 영어로 번역해 버리므로
            #    감지된 언어로 받아쓴다 – 번역 방지. 감지 확률이 낮으면(0.5 미만) 요청한 언어를 그대로 쓴다.
            audio = whisper.pad_or_trim(whisper.load_audio(path))
            mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)   # large-v3 는 128, 나머지는 80
            _, probs = model.detect_language(mel)
            detected, prob = max(probs.items(), key=lambda kv: kv[1])
            language = detected if prob >= 0.5 else body.language

        # 2) 받아쓰기 (task=transcribe 는 기본값. language 가 실제 말과 같으면 번역이 일어나지 않는다)
        result = model.transcribe(path, language=language, fp16=True, temperature=0.0)
        segs = result.get("segments") or []
        avg_logprob = sum(s.get("avg_logprob", -999.0) for s in segs) / len(segs) if segs else -999.0
        return {"text": result["text"].strip(), "avg_logprob": avg_logprob,
                "language": language, "detected": detected, "language_prob": round(float(prob), 3) if prob is not None else None,
                "requested": body.language}
    finally:
        if path:
            os.unlink(path)


@app.get("/health")
def health():
    return {"ok": True, "models_loaded": list(_models.keys()), "device": DEVICE}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
