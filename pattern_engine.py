"""Pattern engine: chase, front-to-back, left-off, music-color, swirl, breathing, etc."""

import math
import time
from dataclasses import dataclass
from enum import Enum

from audio_engine import (
    FrequencyBands,
    bands_to_hue,
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
    LEFT_RIGHT_ALT = "left_right_alt"      # left and right zones alternate pulsing
    CENTER_OUT = "center_out"              # within each zone: middle lights first, expand outward
    UPPER_BASS = "upper_bass"
    BASS_FLOOD = "bass_flood"      # low freq drives brightness (flood lights)
    TREBLE_HUE = "treble_hue"      # high freq drives hue shift
    BAND_SPLIT = "band_split"      # bass→intensity, treble→hue (classic mapping)
    MUSIC_COLOR = "music_color"
    BREATHING = "breathing"
    ALL_ON = "all_on"
    ZONE_MIX = "zone_mix"          # different pattern per zone, cycles over time
    BEAT_HUE = "beat_hue"          # hue jumps on beat detection; intensity pulses with bass


@dataclass
class LightState:
    """Per-light state: color (r,g,b), intensity (0-1), optional rotation_y (radians)."""

    r: float
    g: float
    b: float
    intensity: float
    rotation_y: float | None = None  # radians, Y-axis; None = no rotation update


def _base_color() -> tuple[float, float, float]:
    return (1.0, 0.5, 0.2)  # warm white/orange default


class PatternEngine:
    """
    Generates LightState for each light based on pattern and audio.
    """

    # Default zone mix sets: cycle these so top/sides do different things
    DEFAULT_ZONE_MIX_SETS = [
        {"top": "chase", "left": "left_off", "right": "right_off", "front": "bass_flood", "back": "center_out", "bottom": "bass_flood"},
        {"top": "center_out", "left": "chase", "right": "chase", "front": "left_right_alt", "back": "music_color", "bottom": "music_color"},
        {"top": "swirl", "left": "bass_flood", "right": "bass_flood", "front": "center_out", "back": "left_off", "bottom": "left_right_alt"},
        {"top": "music_color", "left": "left_right_alt", "right": "left_right_alt", "front": "chase", "back": "right_off", "bottom": "center_out"},
    ]

    def __init__(
        self,
        layout: LightLayout,
        chase_tail: int = 3,
        rotation_enabled: bool = False,
        rotation_speed: float = 30.0,
        rotation_audio_boost: bool = True,
        zone_mix_sets: list[dict] | None = None,
        zone_cycle_seconds: float = 14.0,
    ):
        self.layout = layout
        self.chase_tail = chase_tail
        self.rotation_enabled = rotation_enabled
        self.rotation_speed = rotation_speed  # deg/sec
        self.rotation_audio_boost = rotation_audio_boost
        self.zone_mix_sets = zone_mix_sets or self.DEFAULT_ZONE_MIX_SETS
        self.zone_cycle_seconds = zone_cycle_seconds
        self._start_time = time.perf_counter()
        # Beat detection state
        self._prev_bass = 0.0
        self._beat_hue = 0.0
        self._last_beat_time = 0.0
        self._beat_cooldown = 0.15  # min seconds between beats

    def _detect_beat(self, bands: FrequencyBands | None) -> bool:
        """Return True if a beat (bass/upper_bass spike) was detected this frame."""
        if not bands:
            return False
        bass = getattr(bands, "upper_bass", bands.low)
        t = time.perf_counter() - self._start_time
        # Beat = sharp rise and we're past cooldown
        rise = bass - self._prev_bass
        self._prev_bass = bass
        if rise > 0.25 and (t - self._last_beat_time) >= self._beat_cooldown and bass > 0.3:
            self._last_beat_time = t
            return True
        return False

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

    def _left_right_alt_intensity(
        self, ld: LightDescriptor, phase: float, bands: FrequencyBands | None
    ) -> float:
        """
        Left and right zones alternate: left on when phase 0-0.5, right on 0.5-1.
        Front/back/top/bottom pulse with overall or split (left half vs right half by zone).
        """
        if ld.zone == Zone.LEFT:
            return 1.0 if phase < 0.5 else 0.0
        if ld.zone == Zone.RIGHT:
            return 0.0 if phase < 0.5 else 1.0
        # Front/back/top/bottom: left half of zone = left phase, right half = right phase
        mid = ld.zone_count / 2
        on_left_phase = phase < 0.5
        on_right_phase = phase >= 0.5
        if ld.zone_index < mid:
            base = 1.0 if on_left_phase else 0.0
        else:
            base = 1.0 if on_right_phase else 0.0
        if bands:
            base *= 0.4 + 0.6 * bands.overall
        return base

    def _center_out_intensity(
        self, ld: LightDescriptor, phase: float, bands: FrequencyBands | None
    ) -> float:
        """
        Within each zone: middle 2 lights on first, expand outward by 1 each side.
        Phase 0 = center 2; phase 0.2 = middle 4; ... phase 1 = full zone.
        """
        if ld.zone_count <= 0:
            return 0.0
        center = (ld.zone_count - 1) / 2.0
        dist_from_center = abs(ld.zone_index - center)
        max_radius = center + 0.5  # full zone
        min_radius = 0.5  # middle 2 lights
        if bands:
            phase = (phase * 0.7 + 0.3 * getattr(bands, "upper_bass", bands.low)) % 1.0
        lit_radius = min_radius + phase * (max_radius - min_radius)
        if dist_from_center <= lit_radius:
            return max(0.0, 1.0 - (dist_from_center / max(lit_radius, 0.01)) * 0.3)
        return 0.0

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
        # Hue drifts slowly through full spectrum (not stuck in red/orange)
        hue_shift = (t * 0.12) % 1.0
        base_hue = rgb_to_hue(base_color[0], base_color[1], base_color[2])
        hue = (base_hue + hue_shift) % 1.0
        color = hue_to_rgb(hue, 0.85, 0.9)
        return color, breath

    def _rotation_y(self, bands: FrequencyBands | None) -> float | None:
        """Current Y rotation in radians, or None if rotation disabled."""
        if not self.rotation_enabled:
            return None
        t = time.perf_counter() - self._start_time
        deg_per_sec = self.rotation_speed
        if self.rotation_audio_boost and bands:
            deg_per_sec *= 0.7 + 0.6 * bands.low
        angle_deg = (t * deg_per_sec) % 360
        return math.radians(angle_deg)

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

        # Music-reactive color - spread across full spectrum (not just red/orange)
        t = time.perf_counter() - self._start_time
        time_hue = (t * 0.08) % 1.0  # slow drift through spectrum
        if bands:
            band_hue = bands_to_hue(bands)  # low=red, mid=green, high=blue
            base_hue = (band_hue * 0.6 + time_hue * 0.4) % 1.0
            music_color = energy_to_color(bands.mid, base_hue)
        else:
            base_hue = time_hue
            music_color = energy_to_color(0.6, base_hue)

        rotation_y = self._rotation_y(bands)

        # Breathing: compute once, same for all lights
        if pattern == Pattern.BREATHING:
            breath_color, breath_intensity = self._breathing_state(music_color)
            return [
                LightState(
                    r=breath_color[0], g=breath_color[1], b=breath_color[2],
                    intensity=breath_intensity, rotation_y=rotation_y,
                )
                for _ in self.layout.iter_lights()
            ]

        # ZONE_MIX: different pattern per zone, cycling sets over time
        if pattern == Pattern.ZONE_MIX:
            t = time.perf_counter() - self._start_time
            set_idx = int(t / self.zone_cycle_seconds) % max(1, len(self.zone_mix_sets))
            zone_set = self.zone_mix_sets[set_idx]

        for ld in self.layout.iter_lights():
            intensity = 0.0
            # Per-light hue offset so adjacent lights vary (rainbow spread)
            light_hue_offset = (ld.global_index / max(n, 1)) * 0.2
            base_hue_adj = (base_hue + light_hue_offset) % 1.0
            color = energy_to_color(bands.mid if bands else 0.6, base_hue_adj)

            # For ZONE_MIX, use zone's pattern from current set
            p = pattern
            if pattern == Pattern.ZONE_MIX:
                zone_pattern_str = zone_set.get(ld.zone.value, "bass_flood")
                try:
                    p = Pattern(zone_pattern_str)
                except ValueError:
                    p = Pattern.BASS_FLOOD

            if p == Pattern.CHASE:
                intensity = self._chase_intensity(ld, phase, self.chase_tail, False)
            elif p == Pattern.CHASE_REVERSE:
                intensity = self._chase_intensity(ld, phase, self.chase_tail, True)
            elif p == Pattern.FRONT_TO_BACK:
                intensity = self._front_to_back_intensity(ld, phase, False)
            elif p == Pattern.BACK_TO_FRONT:
                intensity = self._front_to_back_intensity(ld, phase, True)
            elif p == Pattern.LEFT_OFF:
                intensity = self._left_off_intensity(ld)
            elif p == Pattern.RIGHT_OFF:
                intensity = self._right_off_intensity(ld)
            elif p == Pattern.LEFT_RIGHT_ALT:
                intensity = self._left_right_alt_intensity(ld, phase, bands)
            elif p == Pattern.CENTER_OUT:
                intensity = self._center_out_intensity(ld, phase, bands)
            elif p == Pattern.SWIRL:
                intensity = self._swirl_intensity(ld, phase, self.chase_tail, bands)
            elif p == Pattern.UPPER_BASS:
                intensity = 0.3 + 0.7 * (getattr(bands, "upper_bass", bands.low) if bands else 0.5)
            elif p == Pattern.BASS_FLOOD:
                intensity = 0.2 + 0.8 * (bands.low if bands else 0.5)
            elif p == Pattern.TREBLE_HUE:
                hue = bands_to_hue(bands) if bands else time_hue
                color = energy_to_color(1.0, (hue + light_hue_offset) % 1.0)
                intensity = 0.5 + 0.5 * (bands.overall if bands else 0.5)
            elif p == Pattern.BAND_SPLIT:
                intensity = 0.3 + 0.7 * (bands.low if bands else 0.5)
                hue = bands_to_hue(bands) if bands else time_hue
                color = energy_to_color(0.8, (hue + light_hue_offset) % 1.0)
            elif p == Pattern.MUSIC_COLOR:
                intensity = 0.5 + 0.5 * (bands.overall if bands else 0.5)
            elif p == Pattern.ALL_ON:
                intensity = 1.0
            elif p == Pattern.BEAT_HUE:
                beat = self._detect_beat(bands)
                if beat:
                    self._beat_hue = (self._beat_hue + 0.2) % 1.0
                hue = (self._beat_hue + light_hue_offset * 0.5) % 1.0
                color = energy_to_color(0.9, hue)
                intensity = 0.3 + 0.7 * (getattr(bands, "low", 0.5) if bands else 0.5)

            # Boost intensity with bass for most patterns
            no_bass_boost = (Pattern.LEFT_OFF, Pattern.RIGHT_OFF, Pattern.LEFT_RIGHT_ALT, Pattern.CENTER_OUT, Pattern.UPPER_BASS, Pattern.BASS_FLOOD, Pattern.BAND_SPLIT, Pattern.BEAT_HUE)
            if bands and p not in no_bass_boost:
                intensity = min(1.0, intensity * (0.7 + 0.3 * bands.low))

            states.append(
                LightState(
                    r=color[0],
                    g=color[1],
                    b=color[2],
                    intensity=intensity,
                    rotation_y=rotation_y,
                )
            )

        return states
