"""Pattern engine: chase, front-to-back, left-off, music-color, etc."""

import time
from dataclasses import dataclass
from enum import Enum

from audio_engine import FrequencyBands, energy_to_color
from light_layout import LightLayout, LightDescriptor, Zone


class Pattern(Enum):
    CHASE = "chase"
    FRONT_TO_BACK = "front_to_back"
    LEFT_OFF = "left_off"
    MUSIC_COLOR = "music_color"
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
        self, ld: LightDescriptor, phase: float, tail_len: int
    ) -> float:
        """
        Chase pattern: one lit "head" moves, with a tail of dimming lights.
        tail_len = number of lights in the tail (e.g. 2-3).
        """
        n = self.layout.total_lights()
        if n == 0:
            return 0.0
        head_pos = phase * n
        dist = (ld.global_index - head_pos + n) % n
        if dist <= tail_len:
            return 1.0 - (dist / (tail_len + 1))
        return 0.0

    def _front_to_back_intensity(self, ld: LightDescriptor, phase: float) -> float:
        """
        Front-to-back wave: front lights light first, then back.
        Uses zones: front -> left/right -> back. Top/bottom follow their row.
        """
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
        """Left lights off, right lights on (or vice versa - configurable)."""
        if ld.zone == Zone.LEFT:
            return 0.0
        return 1.0

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

        for ld in self.layout.iter_lights():
            intensity = 0.0
            color = music_color

            if pattern == Pattern.CHASE:
                intensity = self._chase_intensity(ld, phase, self.chase_tail)
            elif pattern == Pattern.FRONT_TO_BACK:
                intensity = self._front_to_back_intensity(ld, phase)
            elif pattern == Pattern.LEFT_OFF:
                intensity = self._left_off_intensity(ld)
            elif pattern == Pattern.MUSIC_COLOR:
                # All on, color from music
                intensity = 0.5 + 0.5 * (bands.overall if bands else 0.5)
            elif pattern == Pattern.ALL_ON:
                intensity = 1.0

            # Boost intensity with bass for most patterns
            if bands and pattern != Pattern.LEFT_OFF:
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
