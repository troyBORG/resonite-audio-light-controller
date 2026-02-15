"""Audio processing: FFT, frequency bands, and color mapping for reactive lighting."""

import math
from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass
class FrequencyBands:
    """Energy levels in low, mid, and high frequency bands (0-1 normalized)."""

    low: float  # bass 20-250 Hz
    upper_bass: float  # upper bass 60-150 Hz (punch, kick)
    mid: float  # mids 250-2000 Hz
    high: float  # treble 2000-20000 Hz
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
    upper_bass_e = band_energy(60, 150)
    mid_e = band_energy(250, 2000)
    high_e = band_energy(2000, 20000)
    overall_e = band_energy(20, 20000)

    # Normalize to 0-1 range (clip and scale based on typical levels)
    scale = 1.0 / max(1e-6, max(low_e, upper_bass_e, mid_e, high_e, overall_e) * 2.0)
    return FrequencyBands(
        low=min(1.0, low_e * scale),
        upper_bass=min(1.0, upper_bass_e * scale),
        mid=min(1.0, mid_e * scale),
        high=min(1.0, high_e * scale),
        overall=min(1.0, overall_e * scale),
    )


def energy_to_hue(energy: float, base_hue: float = 0.0) -> float:
    """Map energy (0-1) to hue. base_hue + energy spans wider spectrum for color variety."""
    return (base_hue + energy * 0.7) % 1.0


def rgb_to_hue(r: float, g: float, b: float) -> float:
    """Convert RGB to hue 0-1. Returns 0 if color is achromatic."""
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx == mn:
        return 0.0
    d = mx - mn
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h / 6) % 1.0


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
    saturation = 0.85
    value = 0.35 + 0.65 * energy
    return hue_to_rgb(hue, saturation, value)


def bands_to_hue(bands: "FrequencyBands") -> float:
    """Map frequency bands to hue across full spectrum: low=red, mid=green, high=blue."""
    # Low=0, Mid=0.33, High=0.66, blend by energy
    low_w = bands.low
    mid_w = bands.mid
    high_w = bands.high
    total = low_w + mid_w + high_w + 1e-6
    hue = (0.0 * low_w + 0.33 * mid_w + 0.66 * high_w) / total
    return hue % 1.0


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
