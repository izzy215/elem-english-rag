"""
발음 파형 비교 (참고용, PRD 범위 밖 실험 기능)  

speak.py 가 내부적으로만 쓰는 헬퍼 모듈. 새 API 엔드포인트는 X.

사용법:
    from backend.pronounce import pronunciation_score
    score = pronunciation_score(ref_wav_path, audio_base64, mime)  # 0~100

그냥 "소리 형태가 얼마나 비슷한가" 정도의 참고 지표.
- 완전히 다른 문장/단어 : 확실히 구분 (정확 21~26 vs 오답 28~33대)
- 같은 단어인데 심하게 웅얼거려 STT도 실패할 정도 : 확실히 구분 (거리 30대)
- 같은 단어를 살짝 부정확하게 발음한 정도의 미세한 차이 : 신호가 약하고 거의 안 갈림
BASELINE·SCALE 은 실측 데이터로 튜닝한 값.
"""
import base64
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np
import torch
import whisper
from silero_vad import collect_chunks, get_speech_timestamps, load_silero_vad

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
_ENCODER_FRAME_RATE = 50  # whisper 인코더는 30초를 1500프레임으로 인코딩 = 초당 50프레임

_whisper_encoder = None


def _get_whisper_encoder():
    global _whisper_encoder
    if _whisper_encoder is None:
        _whisper_encoder = whisper.load_model("base")
    return _whisper_encoder

# 실제 목소리 16개(정확 8개 distance 21.4~26.0, 오답 8개 distance 28.4~33.3)로
# 튜닝한 값. score = BASELINE - distance*SCALE, 두 그룹 경계값(21.4→약 87점, 33.3→약 8점)
# 두 점을 직선으로 잇는 방식으로 계산. 데이터가 더 쌓이면 재조정 필요.
BASELINE = 230.0
SCALE = 6.667

_vad_model = None


def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        _vad_model = load_silero_vad()
    return _vad_model


def _vad_trim(y: np.ndarray, sr: int) -> np.ndarray:
    """webrtcvad 대신 쓰는 신경망 기반 음성 구간 검출 (librosa.effects.trim 대체).
    음성 구간만 남기고 앞뒤 무음 제거. 음성 구간이 없으면 길이 0 반환.
    """
    audio = torch.from_numpy(y.astype(np.float32))
    model = _get_vad_model()
    timestamps = get_speech_timestamps(audio, model, sampling_rate=sr)
    if not timestamps:
        return y[:0]
    return collect_chunks(timestamps, audio).numpy()


def _decode_to_wav_array(audio_bytes: bytes, ext: str):
    """webm/opus 등 soundfile 이 못 읽는 포맷을 ffmpeg로 wav(16kHz mono)로 변환한 뒤 로드.

    """
    src = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    dst = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    src.write(audio_bytes)
    src.close()
    dst.close()
    try:
        subprocess.run(
            [_FFMPEG, "-y", "-i", src.name, "-ar", "16000", "-ac", "1", dst.name],
            check=True, capture_output=True,
        )
        return librosa.load(dst.name, sr=16000)
    finally:
        Path(src.name).unlink(missing_ok=True)
        Path(dst.name).unlink(missing_ok=True)


def _features_whisper(y: np.ndarray, sr: int) -> np.ndarray:
    """직접 만든 MFCC 대신, 이미 로드된 Whisper 인코더의 은닉 표현을 특징으로 씀.
    Whisper 인코더는 30초를 1500프레임으로 인코딩 = 초당 50프레임. librosa dtw 는 (특징, 시간) 축 순서를 기대.
    """
    duration_sec = len(y) / sr
    mel = whisper.log_mel_spectrogram(y.astype(np.float32))
    mel = whisper.pad_or_trim(mel, whisper.audio.N_FRAMES)
    model = _get_whisper_encoder()
    with torch.no_grad():
        emb = model.encoder(mel.unsqueeze(0))[0].numpy()  # [1500, 512]
    n_frames = max(1, min(emb.shape[0], int(duration_sec * _ENCODER_FRAME_RATE) + 2))
    return emb[:n_frames].T  # [512, n_frames] — librosa dtw 는 (특징, 시간) 축 순서를 기대


def pronunciation_score(ref_wav_path: str, audio_base64: str, mime: str) -> int:
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    student, sr = _decode_to_wav_array(audio_bytes, ext)

    ref, _ = librosa.load(ref_wav_path, sr=16000)

    ref = _vad_trim(ref, sr)
    student = _vad_trim(student, sr)

    if len(ref) == 0 or len(student) == 0:
        return 0

    feat_ref = _features_whisper(ref, sr)
    feat_stu = _features_whisper(student, sr)

    D, _ = librosa.sequence.dtw(feat_ref, feat_stu)
    distance = D[-1, -1] / max(D.shape)
    return int(np.clip(BASELINE - distance * SCALE, 0, 100))


# 텍스트가 맞은 경우(passed=True)에만 쓰는 3단계 표시용 경계값.
# 실측 데이터에서 "텍스트가 맞은" 케이스의 점수가 대략 55~87 사이였던 것 기준.
LEVEL_HIGH = 70   # 이상 → 상
LEVEL_MID = 50    # 이상 → 중, 미만 → 하


def pronunciation_level(score: int) -> str:
    """0~100 점수를 "상/중/하" 3단계로 바꾼다. text 채점이 통과(passed=True)했을 때만 쓴다 —
    미세한 발음 차이는 신뢰도가 낮아서, 숫자 그대로 보여주는 대신 큰 단계로만 표현한다."""
    if score >= LEVEL_HIGH:
        return "상"
    if score >= LEVEL_MID:
        return "중"
    return "하"
