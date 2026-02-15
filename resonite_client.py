"""ResoniteLink WebSocket client: create and update lights in Resonite."""

import asyncio
import logging
import math
import json
import uuid
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from light_layout import LightLayout, LightDescriptor, Zone
from pattern_engine import LightState

logger = logging.getLogger(__name__)
ID_PREFIX = "RALC_"
# FrooxEngine.Light handles Point/Spot/Directional via LightType enum
LIGHT_COMPONENT = "[FrooxEngine]FrooxEngine.Light"
# LightType enum values for addComponent: Point, Spot, Directional
LIGHT_TYPE_POINT = "Point"
# Visual mesh for each light (small sphere)
SPHERE_MESH = "[FrooxEngine]FrooxEngine.SphereMesh"
PBS_METALLIC = "[FrooxEngine]FrooxEngine.PBS_Metallic"
MESH_RENDERER = "[FrooxEngine]FrooxEngine.MeshRenderer"
# Bulb sphere: radius 0.1, segments 4, rings 2
SPHERE_RADIUS = 0.1
SPHERE_SEGMENTS = 4
SPHERE_RINGS = 2


def _ref(target_id: str) -> dict:
    return {"$type": "reference", "targetId": target_id}


def _ref_list(*target_ids: str) -> dict:
    """List of references (e.g. for MeshRenderer.Materials)."""
    return {"$type": "list", "elements": [_ref(tid) for tid in target_ids]}


def _float3(x: float, y: float, z: float) -> dict:
    return {"$type": "float3", "value": {"x": x, "y": y, "z": z}}


def _color(r: float, g: float, b: float, a: float = 1.0) -> dict:
    """colorX format per ResoniteLink (Light.Color is Sync<colorX>)."""
    return {"$type": "colorX", "value": {"r": r, "g": g, "b": b, "a": a}}


def _str_val(s: str) -> dict:
    return {"$type": "string", "value": s}


def _float_val(v: float) -> dict:
    return {"$type": "float", "value": v}


def _bool_val(v: bool) -> dict:
    return {"$type": "bool", "value": v}


def _int_val(v: int) -> dict:
    return {"$type": "int", "value": v}


def _enum_val(enum_type: str, value: str) -> dict:
    """ResoniteLink enum field (e.g. LightType = Point)."""
    return {"$type": "enum", "value": value, "enumType": enum_type}


def _floatQ(x: float, y: float, z: float, w: float) -> dict:
    """Quaternion for slot rotation."""
    return {"$type": "floatQ", "value": {"x": x, "y": y, "z": z, "w": w}}


def euler_y_to_quat(angle_rad: float) -> dict:
    """Rotation around Y axis (up) - angle in radians."""
    half = angle_rad / 2
    return _floatQ(0, math.sin(half), 0, math.cos(half))


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
        self._send_lock = asyncio.Lock()

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
        async with self._send_lock:
            await self._ws.send(json.dumps(msg))
            try:
                resp = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
                return json.loads(resp)
            except asyncio.TimeoutError:
                return None

    def _check_response(self, resp: dict | None, op: str, context: str = "") -> None:
        """Log and raise if response indicates error."""
        if resp is None:
            logger.warning("%s %s: no response (timeout)", op, context)
            return
        err = resp.get("errorInfo")
        if err:
            msg = f"{op} {context}: {err}"
            logger.error(msg)
            raise RuntimeError(msg)

    async def setup_lights(
        self,
        layout: LightLayout,
        parent_slot_id: str | None = None,
        center_x: float = 0,
        center_y: float = 0,
        center_z: float = 0,
    ) -> None:
        """
        Create the light hierarchy in Resonite.
        parent_slot_id: slot to parent under (e.g. DJ booth). None = Root.
        center_*: offset all positions (e.g. around DJ booth).
        """
        self._layout = layout
        root_id = f"{ID_PREFIX}Root_{uuid.uuid4().hex[:8]}"
        self._root_slot_id = root_id
        parent = _ref(parent_slot_id or "Root")

        r = await self._send({
            "$type": "addSlot",
            "data": {
                "id": root_id,
                "parent": parent,
                "name": _str_val("Audio Lights"),
            },
        })
        self._check_response(r, "addSlot", root_id)

        # Add DynamicVariableSpace for tagging/organization
        space_id = f"{ID_PREFIX}Space_{uuid.uuid4().hex[:8]}"
        r = await self._send({
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
        self._check_response(r, "addComponent", "DynamicVariableSpace")

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
            offset = (ld.zone_index - ld.zone_count / 2) * 0.5
            if ld.zone in (Zone.LEFT, Zone.RIGHT):
                x, y, z = base_x, base_y + offset, base_z
            elif ld.zone in (Zone.FRONT, Zone.BACK):
                x, y, z = base_x + offset, base_y, base_z
            else:
                x, y, z = base_x + offset, base_y, base_z
            x += center_x
            y += center_y
            z += center_z

            slot_id = f"{ID_PREFIX}Light_{ld.global_index}_{uuid.uuid4().hex[:6]}"
            comp_id = f"{ID_PREFIX}Comp_{ld.global_index}_{uuid.uuid4().hex[:6]}"

            r = await self._send({
                "$type": "addSlot",
                "data": {
                    "id": slot_id,
                    "parent": _ref(root_id),
                    "name": _str_val(f"Light_{ld.zone.value}_{ld.zone_index}"),
                    "position": _float3(x, y, z),
                    "scale": _float3(1, 1, 1),
                },
            })
            self._check_response(r, "addSlot", slot_id)

            r = await self._send({
                "$type": "addComponent",
                "containerSlotId": slot_id,
                "data": {
                    "id": comp_id,
                    "componentType": LIGHT_COMPONENT,
                    "members": {
                        "LightType": _enum_val("LightType", LIGHT_TYPE_POINT),
                        "Color": _color(1, 0.5, 0.2),
                        "Intensity": _float_val(1.0),
                        "Range": _float_val(10.0),
                    },
                },
            })
            self._check_response(r, "addComponent", comp_id)

            # Visual: small sphere so you can see where each light is
            mesh_id = f"{ID_PREFIX}Mesh_{ld.global_index}_{uuid.uuid4().hex[:6]}"
            mat_id = f"{ID_PREFIX}Mat_{ld.global_index}_{uuid.uuid4().hex[:6]}"
            renderer_id = f"{ID_PREFIX}Rend_{ld.global_index}_{uuid.uuid4().hex[:6]}"
            bulb_color = (1.0, 0.5, 0.2)

            r = await self._send({
                "$type": "addComponent",
                "containerSlotId": slot_id,
                "data": {
                    "id": mesh_id,
                    "componentType": SPHERE_MESH,
                    "members": {
                        "Radius": _float_val(SPHERE_RADIUS),
                        "Segments": _int_val(SPHERE_SEGMENTS),
                        "Rings": _int_val(SPHERE_RINGS),
                    },
                },
            })
            self._check_response(r, "addComponent", mesh_id)

            r = await self._send({
                "$type": "addComponent",
                "containerSlotId": slot_id,
                "data": {
                    "id": mat_id,
                    "componentType": PBS_METALLIC,
                    "members": {"AlbedoColor": _color(*bulb_color)},
                },
            })
            self._check_response(r, "addComponent", mat_id)

            r = await self._send({
                "$type": "addComponent",
                "containerSlotId": slot_id,
                "data": {"id": renderer_id, "componentType": MESH_RENDERER, "members": {}},
            })
            self._check_response(r, "addComponent", renderer_id)

            r = await self._send({
                "$type": "updateComponent",
                "data": {
                    "id": renderer_id,
                    "members": {
                        "Mesh": _ref(mesh_id),
                        "Materials": _ref_list(mat_id),
                    },
                },
            })
            self._check_response(r, "updateComponent", renderer_id)

            self._slot_ids.append(slot_id)
            self._component_ids.append(comp_id)

    async def update_lights(self, states: list[LightState]) -> None:
        """Send updateComponent (and updateSlot for rotation) for each light (parallel)."""
        tasks = []
        for i, state in enumerate(states):
            if i >= len(self._component_ids):
                break
            comp_id = self._component_ids[i]
            slot_id = self._slot_ids[i] if i < len(self._slot_ids) else None
            intensity = max(0.0, min(1.0, state.intensity))
            msg = {
                "$type": "updateComponent",
                "data": {
                    "id": comp_id,
                    "members": {
                        "Color": _color(state.r, state.g, state.b),
                        "Intensity": _float_val(intensity * 2.0),
                    },
                },
            }
            tasks.append(self._send(msg))
            if slot_id is not None and state.rotation_y is not None:
                rot_msg = {
                    "$type": "updateSlot",
                    "data": {
                        "id": slot_id,
                        "rotation": euler_y_to_quat(state.rotation_y),
                    },
                }
                tasks.append(self._send(rot_msg))
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
