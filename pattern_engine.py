"""Pattern engine: chase, front-to-back, left-off, music-color, swirl, breathing, etc."""

import math
import time
from dataclasses import dataclass
from enum import Enum

from audio_engine import (
    FrequencyBands,
    energy_to_color,
    hue_to_rgb,
    rgb_to_hue,
)
from light_layout import LightLayout, LightDescriptor, Zone


class Pattern(Enum):
    CHASE = "chase"
    CHASE_REVERSE = "chase_reverse"
    SWIRL = "swirl"
    FRONT_TO_BACK = "front_to_back"
    BACK_TO_FRONT = "back_to_front"
    LEFT_OFF = "left_off"
    RIGHT_OFF = "right_off"
    UPPER_BASS = "upper_bass"
    MUSIC_COLOR = "music_color"
    BREATHING = "breathing"
    ALL_ON = "all_on"


@dataclass
class LightState:
    """Per-light state: color (r,g,b) and intensity (0-1)."""

    r: float
    g: float
    b: float
    intensity: float


def _base_color() -> tuple[float, float, float]:
    return (1.0, 0.5, 0.2)  # warm white/orange default


class PatternEngine:
    """
    Generates LightState for each light based on pattern and audio.
    """

    def __init__(
        self,
        layout: LightLayout,
        chase_tail: int = 3,
    ):
        self.layout = layout
        self.chase_tail = chase_tail
        self._start_time = time.perf_counter()

    def _phase(self, speed: float = 1.0) -> float:
        """Oscillating phase 0-1 based on time."""
        t = time.perf_counter() - self._start_time
        phase = (t * speed) % 1.0
        return phase

    def _chase_intensity(
        self, ld: LightDescriptor, phase: float, tail_len: int, reverse: bool = False
    ) -> float:
        """
        Chase pattern: one lit "head" moves, with a tail of dimming lights.
        tail_len = number of lights in the tail (e.g. 2-3).
        """
        n = self.layout.total_lights()
        if n == 0:
            return 0.0
        if reverse:
            phase = 1.0 - phase
        head_pos = phase * n
        dist = (ld.global_index - head_pos + n) % n
        if dist <= tail_len:
            return 1.0 - (dist / (tail_len + 1))
        return 0.0

    def _front_to_back_intensity(
        self, ld: LightDescriptor, phase: float, reverse: bool = False
    ) -> float:
        """
        Front-to-back wave: front lights light first, then back.
        Uses zones: front -> left/right -> back. Top/bottom follow their row.
        """
        if reverse:
            phase = 1.0 - phase
        zone_order = [Zone.FRONT, Zone.LEFT, Zone.RIGHT, Zone.BACK, Zone.TOP, Zone.BOTTOM]
        try:
            zone_phase = zone_order.index(ld.zone) / len(zone_order)
        except ValueError:
            zone_phase = 0
        within_zone = ld.zone_index / max(1, ld.zone_count)
        wave_pos = (zone_phase * 0.5 + within_zone * 0.5) % 1.0
        dist = abs(wave_pos - phase)
        if dist > 0.5:
            dist = 1.0 - dist
        return max(0, 1.0 - dist * 3)

    def _left_off_intensity(self, ld: LightDescriptor) -> float:
        """Left lights off, right lights on."""
        if ld.zone == Zone.LEFT:
            return 0.0
        return 1.0

    def _right_off_intensity(self, ld: LightDescriptor) -> float:
        """Right lights off, left lights on."""
        if ld.zone == Zone.RIGHT:
            return 0.0
        return 1.0

    def _swirl_intensity(
        self, ld: LightDescriptor, phase: float, tail_len: int, bands: FrequencyBands | None
    ) -> float:
        """
        Swirl: circular rotating chase. All lights treated as a ring.
        Speed can be boosted by upper bass for a vortex feel.
        """
        n = self.layout.total_lights()
        if n == 0:
            return 0.0
        # Modulate phase speed with upper bass (or low) for reactive swirl
        if bands:
            speed_boost = 0.7 + 0.6 * getattr(bands, "upper_bass", bands.low)
            phase = (phase * speed_boost) % 1.0
        head_pos = phase * n
        dist = (ld.global_index - head_pos + n) % n
        if dist <= tail_len:
            return 1.0 - (dist / (tail_len + 1))
        return 0.0

    def _breathing_state(
        self, base_color: tuple[float, float, float], breath_rate: float = 0.35
    ) -> tuple[tuple[float, float, float], float]:
        """
        Breathing: lock to base color, subtle hue shift, intensity pulses.
        Returns (color, intensity) for all lights (same).
        """
        t = time.perf_counter() - self._start_time
        # Soft sine for intensity (breath in/out)
        breath = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * breath_rate))
        # Subtle hue shift over time (±0.06)
        hue_shift = 0.06 * math.sin(t * 0.5)
        base_hue = rgb_to_hue(base_color[0], base_color[1], base_color[2])
        hue = (base_hue + hue_shift) % 1.0
        color = hue_to_rgb(hue, 0.85, 0.9)
        return color, breath

    def compute(
        self,
        pattern: Pattern,
        bands: FrequencyBands | None,
    ) -> list[LightState]:
        """
        Compute LightState for each light.
        bands can be None for patterns that don't use audio.
        """
        phase = self._phase()
        states: list[LightState] = []
        n = self.layout.total_lights()

        if n == 0:
            return []

        # Music-reactive color
        if bands:
            base_hue = bands.overall * 0.5
            music_color = energy_to_color(bands.mid, base_hue)
        else:
            music_color = _base_color()

        # Breathing: compute once, same for all lights
        if pattern == Pattern.BREATHING:
            breath_color, breath_intensity = self._breathing_state(music_color)
            return [
                LightState(r=breath_color[0], g=breath_color[1], b=breath_color[2], intensity=breath_intensity)
                for _ in self.layout.iter_lights()
            ]

        for ld in self.layout.iter_lights():
            intensity = 0.0
            color = music_color

            if pattern == Pattern.CHASE:
                intensity = self._chase_intensity(ld, phase, self.chase_tail, False)
            elif pattern == Pattern.CHASE_REVERSE:
                intensity = self._chase_intensity(ld, phase, self.chase_tail, True)
            elif pattern == Pattern.FRONT_TO_BACK:
                intensity = self._front_to_back_intensity(ld, phase, False)
            elif pattern == Pattern.BACK_TO_FRONT:
                intensity = self._front_to_back_intensity(ld, phase, True)
            elif pattern == Pattern.LEFT_OFF:
                intensity = self._left_off_intensity(ld)
            elif pattern == Pattern.RIGHT_OFF:
                intensity = self._right_off_intensity(ld)
            elif pattern == Pattern.SWIRL:
                intensity = self._swirl_intensity(ld, phase, self.chase_tail, bands)
            elif pattern == Pattern.UPPER_BASS:
                # All lights pulse with upper bass (60-150 Hz)
                intensity = 0.3 + 0.7 * (getattr(bands, "upper_bass", bands.low) if bands else 0.5)
            elif pattern == Pattern.MUSIC_COLOR:
                # All on, color from music
                intensity = 0.5 + 0.5 * (bands.overall if bands else 0.5)
            elif pattern == Pattern.ALL_ON:
                intensity = 1.0

            # Boost intensity with bass for most patterns
            no_bass_boost = (Pattern.LEFT_OFF, Pattern.RIGHT_OFF, Pattern.UPPER_BASS)
            if bands and pattern not in no_bass_boost:
                intensity = min(1.0, intensity * (0.7 + 0.3 * bands.low))

            states.append(
                LightState(
                    r=color[0],
                    g=color[1],
                    b=color[2],
                    intensity=intensity,
                )
            )

        return states
