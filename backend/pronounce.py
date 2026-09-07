"""
발음 파형 비교 (참고용, PRD 범위 밖 실험 기능)  

speak.py 가 내부적으로만 쓰는 헬퍼 모듈. 새 API 엔드포인트는 X.

사용법:
    from backend.pronounce import pronunciation_score
    score = pronunciation_score(ref_wav_path, audio_base64, mime)  # 0~100
    level = pronunciation_level(score)                             # "상"/"중"/"하"


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

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# CMVN 정규화된 MFCC의 DTW 거리(대략 3.7~4.7 범위)를 0~100 점수로 바꾸는 값.
# distance=3.7 -> 약 85점, distance=4.7 -> 약 15점 이 되도록 두 점을 직선으로 잇는 방식.
# torch 버전보다 훨씬 적은 데이터로 잡은 값이라 실측하며 재조정이 필요하다.
BASELINE = 344.0
SCALE = 70.0

LEVEL_HIGH = 70   # score 이상 → 상
LEVEL_MID = 50    # score 이상 → 중, 미만 → 하


def pronunciation_level(score: int) -> str:
    """0~100 점수를 "상/중/하" 3단계로 바꾼다. text 채점이 통과(passed=True)했을 때만 쓴다 —
    미세한 발음 차이는 신뢰도가 낮아서, 숫자 그대로 보여주는 대신 큰 단계로만 표현한다."""
    if score >= LEVEL_HIGH:
        return "상"
    if score >= LEVEL_MID:
        return "중"
    return "하"


def _decode_to_wav_array(audio_bytes: bytes, ext: str):
    """webm/opus 등 soundfile 이 못 읽는 포맷을 ffmpeg로 wav(16kHz mono)로 변환한 뒤 로드한다.

    soundfile(libsndfile)이 webm 을 직접 못 읽고("Format not recognised"), librosa 의
    ffmpeg 자동 폴백도 이번 버전 조합에서는 안 걸려서, ffmpeg 변환을 직접 호출한다.
    Windows 에서는 NamedTemporaryFile 을 연 채로 다른 프로세스가 못 열기 때문에
    delete=False 로 만들고 핸들을 닫은 뒤 쓰고, 끝나면 직접 지운다.
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


def _cmvn(mfcc: np.ndarray) -> np.ndarray:
    """켑스트럼 평균-분산 정규화. 계수별로 시간축 평균 0·분산 1로 맞춘다.

    """
    mean = mfcc.mean(axis=1, keepdims=True)
    std = mfcc.std(axis=1, keepdims=True) + 1e-8
    return (mfcc - mean) / std


def _features(y: np.ndarray, sr: int) -> np.ndarray:
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    return _cmvn(mfcc)


def pronunciation_score(ref_wav_path: str, audio_base64: str, mime: str) -> int:
    audio_bytes = base64.b64decode(audio_base64)
    ext = ".webm" if "webm" in mime else ".wav"
    student, sr = _decode_to_wav_array(audio_bytes, ext)

    ref, _ = librosa.load(ref_wav_path, sr=16000)

    ref, _ = librosa.effects.trim(ref)
    student, _ = librosa.effects.trim(student)

    if len(ref) == 0 or len(student) == 0:
        return 0

    feat_ref = _features(ref, sr)
    feat_stu = _features(student, sr)

    D, _ = librosa.sequence.dtw(feat_ref, feat_stu)
    distance = D[-1, -1] / max(D.shape)
    return int(np.clip(BASELINE - distance * SCALE, 0, 100))

