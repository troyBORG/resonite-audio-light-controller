"""ResoniteLink WebSocket client: create and update lights in Resonite."""

import asyncio
import json
import uuid
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from light_layout import LightLayout, LightDescriptor, Zone
from pattern_engine import LightState

ID_PREFIX = "RALC_"
LIGHT_COMPONENT = "[FrooxEngine]FrooxEngine.PointLight"


def _ref(target_id: str) -> dict:
    return {"$type": "reference", "targetId": target_id}


def _float3(x: float, y: float, z: float) -> dict:
    return {"$type": "float3", "value": {"x": x, "y": y, "z": z}}


def _color(r: float, g: float, b: float) -> dict:
    return _float3(r, g, b)


def _str_val(s: str) -> dict:
    return {"$type": "string", "value": s}


def _float_val(v: float) -> dict:
    return {"$type": "float", "value": v}


def _bool_val(v: bool) -> dict:
    return {"$type": "bool", "value": v}


class ResoniteClient:
    """
    Async WebSocket client for ResoniteLink.
    Creates lights in zones and updates them with pattern output.
    """

    def __init__(self, url: str = "ws://localhost:27404/ResoniteLink"):
        self.url = url
        self._ws: WebSocketClientProtocol | None = None
        self._layout: LightLayout | None = None
        self._slot_ids: list[str] = []
        self._component_ids: list[str] = []
        self._root_slot_id: str = ""

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _send(self, msg: dict) -> dict | None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(json.dumps(msg))
        try:
            resp = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            return json.loads(resp)
        except asyncio.TimeoutError:
            return None

    async def setup_lights(self, layout: LightLayout) -> None:
        """
        Create the light hierarchy in Resonite.
        Root -> DynamicVariableSpace -> one slot per light with PointLight.
        """
        self._layout = layout
        root_id = f"{ID_PREFIX}Root_{uuid.uuid4().hex[:8]}"
        self._root_slot_id = root_id

        # Create root slot
        await self._send({
            "$type": "addSlot",
            "data": {
                "id": root_id,
                "parent": _ref("Root"),
                "name": _str_val("Audio Lights"),
            },
        })

        # Add DynamicVariableSpace for tagging/organization
        space_id = f"{ID_PREFIX}Space_{uuid.uuid4().hex[:8]}"
        await self._send({
            "$type": "addComponent",
            "containerSlotId": root_id,
            "data": {
                "id": space_id,
                "componentType": "[FrooxEngine]FrooxEngine.DynamicVariableSpace",
                "members": {
                    "SpaceName": _str_val("AudioLights"),
                },
            },
        })

        self._slot_ids = []
        self._component_ids = []

        # Zone positions (approximate room layout)
        zone_positions: dict[Zone, tuple[float, float, float]] = {
            Zone.LEFT: (-3, 1.5, 0),
            Zone.RIGHT: (3, 1.5, 0),
            Zone.FRONT: (0, 1.5, 3),
            Zone.BACK: (0, 1.5, -3),
            Zone.TOP: (0, 4, 0),
            Zone.BOTTOM: (0, -0.5, 0),
        }

        for ld in layout.iter_lights():
            base_x, base_y, base_z = zone_positions.get(ld.zone, (0, 1.5, 0))
            # Spread lights within zone
            offset = (ld.zone_index - ld.zone_count / 2) * 0.5
            if ld.zone in (Zone.LEFT, Zone.RIGHT):
                x, y, z = base_x, base_y + offset, base_z
            elif ld.zone in (Zone.FRONT, Zone.BACK):
                x, y, z = base_x + offset, base_y, base_z
            else:
                x, y, z = base_x + offset, base_y, base_z

            slot_id = f"{ID_PREFIX}Light_{ld.global_index}_{uuid.uuid4().hex[:6]}"
            comp_id = f"{ID_PREFIX}Comp_{ld.global_index}_{uuid.uuid4().hex[:6]}"

            await self._send({
                "$type": "addSlot",
                "data": {
                    "id": slot_id,
                    "parent": _ref(root_id),
                    "name": _str_val(f"Light_{ld.zone.value}_{ld.zone_index}"),
                    "position": _float3(x, y, z),
                },
            })

            await self._send({
                "$type": "addComponent",
                "containerSlotId": slot_id,
                "data": {
                    "id": comp_id,
                    "componentType": LIGHT_COMPONENT,
                    "members": {
                        "Color": _color(1, 0.5, 0.2),
                        "Intensity": _float_val(1.0),
                        "Range": _float_val(10.0),
                    },
                },
            })

            self._slot_ids.append(slot_id)
            self._component_ids.append(comp_id)

    async def update_lights(self, states: list[LightState]) -> None:
        """Send updateComponent for each light with new color and intensity (parallel)."""
        tasks = []
        for i, state in enumerate(states):
            if i >= len(self._component_ids):
                break
            comp_id = self._component_ids[i]
            intensity = max(0.0, min(1.0, state.intensity))
            msg = {
                "$type": "updateComponent",
                "data": {
                    "id": comp_id,
                    "members": {
                        "Color": _color(state.r, state.g, state.b),
                        "Intensity": _float_val(intensity * 2.0),  # scale for visibility
                    },
                },
            }
            tasks.append(self._send(msg))
        if tasks:
            await asyncio.gather(*tasks)

    async def teardown(self) -> None:
        """Remove our root slot and all lights."""
        if self._root_slot_id:
            await self._send({
                "$type": "removeSlot",
                "slotId": self._root_slot_id,
            })
            self._root_slot_id = ""
            self._slot_ids = []
            self._component_ids = []
