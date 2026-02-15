"""Audio capture from microphone, file, or PipeWire/Pulse source by name."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


def get_default_input_device_index() -> int | None:
    """Return the system default input device index, or None."""
    try:
        default = sd.default.device
        if default is None:
            return None
        if isinstance(default, (tuple, list)) and len(default) >= 1:
            return default[0]
        return default
    except Exception:
        return None


def get_default_input_device_name() -> str:
    """Return the name of the system default input device (for display)."""
    idx = get_default_input_device_index()
    if idx is None:
        return "system default (unknown)"
    try:
        dev = sd.query_devices(idx)
        if hasattr(dev, "get"):
            return dev.get("name", str(dev))
        return str(dev).split("\n")[0].strip() if dev else "unknown"
    except Exception:
        return "unknown"


def list_input_devices() -> list[tuple[int, str]]:
    """Return list of (device_index, name) for all input-capable devices."""
    result = []
    try:
        devices = sd.query_devices()
        for i in range(len(devices)):
            dev = sd.query_devices(i)
            if hasattr(dev, "get"):
                max_in = dev.get("max_input_channels", 0)
                name = dev.get("name", f"Device {i}")
            else:
                max_in = getattr(dev, "max_input_channels", 0)
                name = getattr(dev, "name", str(dev).split("\n")[0])
            if max_in and max_in > 0:
                result.append((i, name))
    except Exception:
        pass
    return result


def get_default_output_device_index() -> int | None:
    """Return the system default output device index, or None."""
    try:
        default = sd.default.device
        if default is None:
            return None
        if isinstance(default, (tuple, list)) and len(default) >= 2:
            return default[1]
        return default
    except Exception:
        return None


def get_default_output_device_name() -> str:
    """Return the name of the system default output device (for display)."""
    idx = get_default_output_device_index()
    if idx is None:
        return "system default (unknown)"
    try:
        dev = sd.query_devices(idx)
        if hasattr(dev, "get"):
            return dev.get("name", str(dev))
        return str(dev).split("\n")[0].strip() if dev else "unknown"
    except Exception:
        return "unknown"


def find_monitor_of_output(output_name: str) -> int | None:
    """
    Find the input device that monitors the given output (e.g. "Yeti", "FiiO", "GA102").
    Returns device index or None if not found. Names are matched case-insensitively.
    """
    output_lower = output_name.lower()
    for idx, name in list_input_devices():
        name_lower = name.lower()
        if "monitor" in name_lower and output_lower in name_lower:
            return idx
    # Some systems name it "Monitor of X" - try partial match
    for idx, name in list_input_devices():
        name_lower = name.lower()
        if "monitor" in name_lower and any(
            part in name_lower for part in output_lower.split()
        ):
            return idx
    return None


def list_output_devices() -> list[tuple[int, str]]:
    """Return list of (device_index, name) for all output-capable devices."""
    result = []
    try:
        devices = sd.query_devices()
        for i in range(len(devices)):
            dev = sd.query_devices(i)
            if hasattr(dev, "get"):
                max_out = dev.get("max_output_channels", 0)
                name = dev.get("name", f"Device {i}")
            else:
                max_out = getattr(dev, "max_output_channels", 0)
                name = getattr(dev, "name", str(dev).split("\n")[0])
            if max_out and max_out > 0:
                result.append((i, name))
    except Exception:
        pass
    return result


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

    def __init__(
        self,
        sample_rate: int,
        chunk_size: int,
        device: int | str | None = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device = device  # None = default, int = index, str = device name
        self._stream: sd.InputStream | None = None

    def _resolve_device(self) -> int | None:
        if self.device is None:
            return None
        if isinstance(self.device, int):
            return self.device
        for idx, name in list_input_devices():
            if self.device in name or name == self.device:
                return idx
        return None

    def get_input_description(self) -> str:
        """Human-readable description of which input is used (for startup message)."""
        if self.device is None:
            return get_default_input_device_name()
        if isinstance(self.device, int):
            try:
                dev = sd.query_devices(self.device)
                return dev.get("name", str(dev)) if hasattr(dev, "get") else str(dev).split("\n")[0]
            except Exception:
                return f"device index {self.device}"
        dev = self._resolve_device()
        if dev is not None:
            try:
                info = sd.query_devices(dev)
                return info.get("name", str(info)) if hasattr(info, "get") else str(info).split("\n")[0]
            except Exception:
                pass
        return str(self.device)

    def start(self) -> None:
        kwargs = dict(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
        )
        dev = self._resolve_device()
        if dev is not None:
            kwargs["device"] = dev
        self._stream = sd.InputStream(**kwargs)
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


class PulseSource:
    """
    Capture from a PipeWire/Pulse source by name using ffmpeg.
    Bypasses PortAudio - uses the exact source you specify.
    """

    def __init__(self, source_name: str, sample_rate: int, chunk_size: int):
        self.source_name = source_name
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._process: subprocess.Popen | None = None
        self._buf = bytearray()

    def get_input_description(self) -> str:
        return self.source_name

    def start(self) -> None:
        self._process = subprocess.Popen(
            [
                "ffmpeg",
                "-f", "pulse",
                "-i", self.source_name,
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "-ac", "1",
                "-ar", str(self.sample_rate),
                "-nostdin",
                "-loglevel", "error",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._buf = bytearray()

    def read(self) -> np.ndarray:
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("ffmpeg not running")
        need = self.chunk_size * 4  # f32le = 4 bytes per sample
        while len(self._buf) < need:
            chunk = self._process.stdout.read(need - len(self._buf))
            if not chunk:
                break
            self._buf.extend(chunk)
        out = bytes(self._buf[:need])
        del self._buf[:need]
        return np.frombuffer(out, dtype=np.float32)

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None


def pulse_source_available() -> bool:
    return shutil.which("ffmpeg") is not None


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

    def get_input_description(self) -> str:
        """Human-readable description (for startup message)."""
        return str(self.path)
