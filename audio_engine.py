"""Audio processing: FFT, frequency bands, and color mapping for reactive lighting."""

import math
from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass
class FrequencyBands:
    """Energy levels in low, mid, and high frequency bands (0-1 normalized)."""

    low: float  # bass
    mid: float  # mids
    high: float  # treble
    overall: float  # full-spectrum energy


def fft_frequency_bands(
    samples: np.ndarray, sample_rate: int, fft_size: int
) -> FrequencyBands:
    """
    Compute FFT and return energy in low/mid/high bands.
    Uses approximate ranges: low 20-250Hz, mid 250-2000Hz, high 2000-20000Hz.
    """
    if len(samples) < fft_size:
        padding = np.zeros(fft_size - len(samples))
        samples = np.concatenate([samples, padding])

    window = np.hanning(fft_size)
    windowed = samples[:fft_size] * window
    fft_result = np.fft.rfft(windowed)
    magnitudes = np.abs(fft_result)

    freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    bin_width = sample_rate / fft_size

    def band_energy(low_hz: float, high_hz: float) -> float:
        low_bin = int(low_hz / bin_width)
        high_bin = min(int(high_hz / bin_width) + 1, len(magnitudes))
        low_bin = max(0, low_bin)
        if high_bin <= low_bin:
            return 0.0
        return float(np.mean(magnitudes[low_bin:high_bin]))

    low_e = band_energy(20, 250)
    mid_e = band_energy(250, 2000)
    high_e = band_energy(2000, 20000)
    overall_e = band_energy(20, 20000)

    # Normalize to 0-1 range (clip and scale based on typical levels)
    scale = 1.0 / max(1e-6, max(low_e, mid_e, high_e, overall_e) * 2.0)
    return FrequencyBands(
        low=min(1.0, low_e * scale),
        mid=min(1.0, mid_e * scale),
        high=min(1.0, high_e * scale),
        overall=min(1.0, overall_e * scale),
    )


def energy_to_hue(energy: float, base_hue: float = 0.0) -> float:
    """Map energy (0-1) to hue shift. Returns hue in 0-1 (maps to 0-360°)."""
    return (base_hue + energy * 0.3) % 1.0


def hue_to_rgb(hue: float, saturation: float = 1.0, value: float = 1.0) -> tuple[float, float, float]:
    """Convert HSV to RGB. Hue in 0-1, returns (r, g, b) in 0-1."""
    h = hue * 6
    i = int(h) % 6
    f = h - int(h)
    p = value * (1 - saturation)
    q = value * (1 - saturation * f)
    t = value * (1 - saturation * (1 - f))
    rgb = [
        (value, t, p),
        (q, value, p),
        (p, value, t),
        (p, q, value),
        (t, p, value),
        (value, p, q),
    ][i]
    return (float(rgb[0]), float(rgb[1]), float(rgb[2]))


def energy_to_color(energy: float, base_hue: float = 0.0) -> tuple[float, float, float]:
    """Map energy to RGB color for lighting. Returns (r, g, b) in 0-1."""
    hue = energy_to_hue(energy, base_hue)
    saturation = 0.9
    value = 0.3 + 0.7 * energy
    return hue_to_rgb(hue, saturation, value)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * max(0, min(1, t))


def lerp_color(
    c1: tuple[float, float, float], c2: tuple[float, float, float], t: float
) -> tuple[float, float, float]:
    """Linear interpolation between two RGB colors."""
    return (
        lerp(c1[0], c2[0], t),
        lerp(c1[1], c2[1], t),
        lerp(c1[2], c2[2], t),
    )
