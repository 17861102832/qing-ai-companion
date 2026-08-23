import base64
import io
import struct
import numpy as np
from pydub import AudioSegment
from pydub.utils import make_chunks
from ..agent.output_types import Actions
from ..agent.output_types import DisplayText


def _wav_bytes_from_numpy(data: np.ndarray, sample_rate: int) -> bytes:
    """把 numpy float PCM 编码成 16-bit WAV 字节流（不依赖 ffmpeg）。"""
    data = np.asarray(data, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]
    pcm = np.clip(data, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype(np.int16)
    n_channels = pcm16.shape[1]
    bytes_per_sample = 2
    byte_rate = sample_rate * n_channels * bytes_per_sample
    block_align = n_channels * bytes_per_sample
    data_bytes = pcm16.tobytes()
    header = b"RIFF" + struct.pack("<I", 36 + len(data_bytes)) + b"WAVE" + \
        b"fmt " + struct.pack("<IHHIIHH", 16, 1, n_channels, sample_rate, byte_rate, block_align, 16) + \
        b"data" + struct.pack("<I", len(data_bytes))
    return header + data_bytes


def _load_audio_robust(audio_path: str):
    """稳健解码音频 → (numpy float32 数组, 采样率)。

    优先用 soundfile（纯 libsndfile，不依赖精简版 ffmpeg 的 mp3 解码），
    若 soundfile 不支持则回退 pydub（可能需要 ffmpeg）。
    这解决了 TRAE 打包的 ffmpeg 缺少 mp3 解码器导致「说话没声音」的问题。
    """
    # 尝试 soundfile
    try:
        import soundfile as sf
        data, sr = sf.read(audio_path, dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)  # 混为单声道
        return data, sr
    except Exception:
        pass
    # 回退 pydub
    audio = AudioSegment.from_file(audio_path)
    arr = np.array(audio.get_array_of_samples(), dtype=np.float32)
    if audio.channels > 1:
        arr = arr.reshape((-1, audio.channels)).mean(axis=1)
    arr /= 32768.0
    return arr, audio.frame_rate


def _get_volume_by_chunks_np(data: np.ndarray, sample_rate: int, chunk_length_ms: int) -> list:
    """基于 numpy 计算分块 RMS 归一化音量（等价 pydub make_chunks+chunk.rms）。"""
    if len(data) == 0:
        raise ValueError("Audio is empty or all zero.")
    chunk_len = max(1, int(sample_rate * chunk_length_ms / 1000.0))
    n = len(data)
    segs = n // chunk_len
    if n % chunk_len != 0:
        segs += 1
    volumes = []
    for i in range(segs):
        seg = data[i * chunk_len:(i + 1) * chunk_len]
        if len(seg) == 0:
            continue
        rms = float(np.sqrt(np.mean(seg ** 2)))
        volumes.append(rms)
    max_volume = max(volumes) if volumes else 0.0
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [v / max_volume for v in volumes]


def _get_volume_by_chunks(audio: AudioSegment, chunk_length_ms: int) -> list:
    """
    Calculate the normalized volume (RMS) for each chunk of the audio.

    Parameters:
        audio (AudioSegment): The audio segment to process.
        chunk_length_ms (int): The length of each audio chunk in milliseconds.

    Returns:
        list: Normalized volumes for each chunk.
    """
    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]


def prepare_audio_payload(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
    forwarded: bool = False,
) -> dict[str, any]:
    """
    Prepares the audio payload for sending to a broadcast endpoint.
    If audio_path is None, returns a payload with audio=None for silent display.

    Parameters:
        audio_path (str | None): The path to the audio file to be processed, or None for silent display
        chunk_length_ms (int): The length of each audio chunk in milliseconds
        display_text (DisplayText, optional): Text to be displayed with the audio
        actions (Actions, optional): Actions associated with the audio

    Returns:
        dict: The audio payload to be sent
    """
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()

    if not audio_path:
        # Return payload for silent display
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions.to_dict() if actions else None,
            "forwarded": forwarded,
        }

    try:
        # 稳健解码：优先 soundfile（纯 libsndfile，不依赖精简 ffmpeg 的 mp3 解码）
        data, sample_rate = _load_audio_robust(audio_path)
        audio_bytes = _wav_bytes_from_numpy(data, sample_rate)
    except Exception as e:
        raise ValueError(
            f"Error loading or converting generated audio file to wav file '{audio_path}': {e}"
        )
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    volumes = _get_volume_by_chunks_np(data, sample_rate, chunk_length_ms)

    payload = {
        "type": "audio",
        "audio": audio_base64,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions.to_dict() if actions else None,
        "forwarded": forwarded,
    }

    return payload


# Example usage:
# payload, duration = prepare_audio_payload("path/to/audio.mp3", display_text="Hello", expression_list=[0,1,2])
