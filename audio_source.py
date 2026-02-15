"""Audio capture from microphone or file."""

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


def read_audio_file(path: str, sample_rate: int) -> tuple[np.ndarray, int]:
    """Read audio file, return (samples, sample_rate). Resample if needed."""
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != sample_rate:
        # Simple resample: linear interpolation
        duration = len(data) / sr
        new_len = int(duration * sample_rate)
        indices = np.linspace(0, len(data) - 1, new_len)
        data = np.interp(indices, np.arange(len(data)), data)
        sr = sample_rate
    return data, sr


class MicrophoneSource:
    """Stream audio from microphone in chunks."""

    def __init__(self, sample_rate: int, chunk_size: int):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
        )
        self._stream.start()

    def read(self) -> np.ndarray:
        if not self._stream:
            raise RuntimeError("Stream not started")
        chunk, _ = self._stream.read(self.chunk_size)
        return chunk.flatten()

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class FileSource:
    """Stream audio from file in chunks (looping)."""

    def __init__(self, path: str, sample_rate: int, chunk_size: int):
        self.path = Path(path)
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._data: np.ndarray | None = None
        self._pos = 0

    def start(self) -> None:
        self._data, _ = read_audio_file(str(self.path), self.sample_rate)
        self._pos = 0

    def read(self) -> np.ndarray:
        if self._data is None:
            raise RuntimeError("File not loaded")
        start = self._pos
        end = start + self.chunk_size
        if end > len(self._data):
            chunk = np.concatenate([
                self._data[start:],
                self._data[: end - len(self._data)],
            ])
            self._pos = end - len(self._data)
        else:
            chunk = self._data[start:end].copy()
            self._pos = end
        return chunk

    def stop(self) -> None:
        self._data = None
        self._pos = 0
