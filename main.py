#!/usr/bin/env python3
"""
Resonite Light Controller (pattern-only)

Pick a pattern, control lights in Resonite. Change patterns in real time by
typing a number (1–18) and Enter. No audio capture.
"""

import argparse
import asyncio
import queue
import sys
import threading
from pathlib import Path

import yaml

from light_layout import LightLayout
from pattern_engine import Pattern, PatternEngine
from resonite_client import ResoniteClient


# Number → pattern for keyboard switching (1–18)
PATTERNS_BY_NUM: dict[int, Pattern] = {i: p for i, p in enumerate(list(Pattern), start=1)}


def load_config(path: str | None = None) -> dict:
    config_path = path or "config.yaml"
    if not Path(config_path).exists():
        config_path = "config.example.yaml"
    if not Path(config_path).exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def run_input_thread(pattern_queue: queue.Queue, stop_event: threading.Event) -> None:
    """Read stdin; on number + Enter, put pattern number in queue."""
    while not stop_event.is_set():
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        n = line.strip()
        if n.isdigit():
            num = int(n)
            if 1 <= num <= len(PATTERNS_BY_NUM):
                pattern_queue.put(num)
            else:
                print(f"  Use 1–{len(PATTERNS_BY_NUM)}")


async def run(
    config: dict,
    pattern_name: str | None = None,
    layout_override: dict | None = None,
    port_override: str | None = None,
) -> None:
    layout = LightLayout.from_dict(layout_override or config.get("layout") or {})
    total = layout.total_lights()
    if total == 0:
        print("No lights in layout. Add counts for left, right, front, back, top.")
        print("Example: layout: { left: 5, right: 5, front: 3, back: 2, top: 4 }")
        sys.exit(1)

    pattern = Pattern(pattern_name or config.get("default_pattern", "chase"))
    chase_tail = config.get("chase_tail", 3)
    update_rate = config.get("update_rate", 30)
    parent_slot_id = config.get("parent_slot_id") or None
    center = config.get("center") or {}
    center_x = float(center.get("x", 0))
    center_y = float(center.get("y", 0))
    center_z = float(center.get("z", 0))
    rotation_enabled = config.get("rotation_enabled", False)
    rotation_speed = float(config.get("rotation_speed", 30))
    rotation_audio_boost = config.get("rotation_audio_boost", True)
    zone_mix_sets = config.get("zone_mix_sets")
    zone_cycle_seconds = float(config.get("zone_cycle_seconds", 14))

    port = port_override or config.get("resonite_port")
    if port is None:
        try:
            port = input("ResoniteLink port (from Resonite): ").strip() or "27404"
        except EOFError:
            port = "27404"
    resonite_url = f"ws://localhost:{port}/ResoniteLink"

    print(f"Layout: {total} lights (L{layout.left} R{layout.right} F{layout.front} B{layout.back} T{layout.top})")
    print(f"Pattern: {pattern.value}")
    print(f"Connecting to Resonite at {resonite_url}...")

    client = ResoniteClient(url=resonite_url)
    try:
        await client.connect()
    except OSError:
        print(f"Invalid port or Resonite not running. Could not connect to {resonite_url}")
        sys.exit(1)

    try:
        await client.setup_lights(
            layout,
            parent_slot_id=parent_slot_id,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
        )
        print(f"Created {total} lights in Resonite.")
    except Exception as e:
        print(f"Failed to create lights: {e}")
        print("Is Resonite running with ResoniteLink enabled?")
        await client.disconnect()
        sys.exit(1)

    pattern_engine = PatternEngine(
        layout,
        chase_tail=chase_tail,
        rotation_enabled=rotation_enabled,
        rotation_speed=rotation_speed,
        rotation_audio_boost=rotation_audio_boost,
        zone_mix_sets=zone_mix_sets,
        zone_cycle_seconds=zone_cycle_seconds,
    )
    interval = 1.0 / update_rate

    pattern_queue: queue.Queue[int] = queue.Queue()
    stop_event = threading.Event()
    input_thread = threading.Thread(target=run_input_thread, args=(pattern_queue, stop_event), daemon=True)
    input_thread.start()

    print()
    print("Type a number (1–18) + Enter to switch pattern. Ctrl+C to stop and clean up.")
    print("  1=chase 2=chase_reverse 3=swirl 4=front_to_back 5=back_to_front")
    print("  6=left_off 7=right_off 8=left_right_alt 9=center_out 10=upper_bass")
    print("  11=bass_flood 12=treble_hue 13=band_split 14=music_color 15=breathing")
    print("  16=all_on 17=zone_mix 18=beat_hue")
    print()

    interrupted = False

    try:
        while True:
            loop_start = asyncio.get_running_loop().time()

            # Check for pattern switch
            try:
                while True:
                    num = pattern_queue.get_nowait()
                    if num in PATTERNS_BY_NUM:
                        pattern = PATTERNS_BY_NUM[num]
                        print(f"→ {pattern.value}")
            except queue.Empty:
                pass

            states = pattern_engine.compute(pattern, None)
            await client.update_lights(states)

            elapsed = asyncio.get_running_loop().time() - loop_start
            await asyncio.sleep(max(0, interval - elapsed))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        stop_event.set()

        # Clean up world (with timeout so we don't hang)
        try:
            await asyncio.wait_for(client.teardown(), timeout=5.0)
        except asyncio.TimeoutError:
            print("Teardown timed out (lights may remain in world)")
        except Exception as e:
            print(f"Teardown error: {e}")

        try:
            await asyncio.wait_for(client.disconnect(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

        print("Stopped." if interrupted else "")


def interactive_layout() -> dict:
    """Prompt user for light counts per zone."""
    zones = ["left", "right", "front", "back", "top", "bottom"]
    layout = {}
    print("Enter number of lights per zone (0 to skip):")
    for z in zones:
        try:
            n = input(f"  {z}: ").strip() or "0"
            layout[z] = int(n)
        except ValueError:
            layout[z] = 0
    return layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Resonite Light Controller (pattern-only)")
    parser.add_argument("--config", "-c", help="Config file path")
    parser.add_argument("--pattern", "-p", choices=[p.value for p in Pattern], help="Initial pattern")
    parser.add_argument("--port", type=str, help="ResoniteLink port (skips prompt)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive layout setup")
    args = parser.parse_args()

    config = load_config(args.config)
    layout_override = None
    if args.interactive:
        layout_override = interactive_layout()

    asyncio.run(run(
        config,
        pattern_name=args.pattern,
        layout_override=layout_override,
        port_override=args.port,
    ))


if __name__ == "__main__":
    main()
