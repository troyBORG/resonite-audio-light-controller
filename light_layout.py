"""Light layout: zones, counts, and indexing for spatial patterns."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class Zone(Enum):
    """Spatial zones for light placement."""

    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass
class LightDescriptor:
    """Single light with zone and index."""

    global_index: int
    zone: Zone
    zone_index: int
    zone_count: int


@dataclass
class LightLayout:
    """
    Defines how many lights are in each zone.
    Used to generate exactly the right number of control signals.
    """

    left: int = 0
    right: int = 0
    front: int = 0
    back: int = 0
    top: int = 0
    bottom: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "LightLayout":
        return cls(
            left=int(d.get("left", 0)),
            right=int(d.get("right", 0)),
            front=int(d.get("front", 0)),
            back=int(d.get("back", 0)),
            top=int(d.get("top", 0)),
            bottom=int(d.get("bottom", 0)),
        )

    def total_lights(self) -> int:
        return (
            self.left + self.right + self.front
            + self.back + self.top + self.bottom
        )

    def iter_lights(self) -> Iterator[LightDescriptor]:
        """Iterate over all lights with zone and index."""
        idx = 0
        for zone, count in [
            (Zone.LEFT, self.left),
            (Zone.RIGHT, self.right),
            (Zone.FRONT, self.front),
            (Zone.BACK, self.back),
            (Zone.TOP, self.top),
            (Zone.BOTTOM, self.bottom),
        ]:
            for zi in range(count):
                yield LightDescriptor(
                    global_index=idx,
                    zone=zone,
                    zone_index=zi,
                    zone_count=count,
                )
                idx += 1

    def zone_count(self, zone: Zone) -> int:
        m = {
            Zone.LEFT: self.left,
            Zone.RIGHT: self.right,
            Zone.FRONT: self.front,
            Zone.BACK: self.back,
            Zone.TOP: self.top,
            Zone.BOTTOM: self.bottom,
        }
        return m.get(zone, 0)

    def lights_in_zone(self, zone: Zone) -> list[int]:
        """Return global indices of all lights in the given zone."""
        return [
            ld.global_index
            for ld in self.iter_lights()
            if ld.zone == zone
        ]
