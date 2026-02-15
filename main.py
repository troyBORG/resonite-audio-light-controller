#!/usr/bin/env python3
"""
Resonite Audio Light Controller

Run the program, type in your light layout (left, right, front, etc.),
and control lights in Resonite with audio-reactive patterns.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from audio_engine import fft_frequency_bands
from audio_source import (
    MicrophoneSource,
    FileSource,
    PulseSource,
    find_monitor_of_output,
    get_default_input_device_index,
    get_default_input_device_name,
    get_default_output_device_index,
    get_default_output_device_name,
    list_input_devices,
    list_output_devices,
    pulse_source_available,
)
from light_layout import LightLayout
from pattern_engine import Pattern, PatternEngine
from resonite_client import ResoniteClient


def load_config(path: str | None = None) -> dict:
    config_path = path or "config.yaml"
    if not Path(config_path).exists():
        config_path = "config.example.yaml"
    if not Path(config_path).exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def parse_layout(config: dict) -> LightLayout:
    layout = config.get("layout") or {}
    return LightLayout.from_dict(layout)


async def run(
    config: dict,
    pattern_name: str | None = None,
    layout_override: dict | None = None,
    demo: bool = False,
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
    sample_rate = config.get("sample_rate", 44100)
    fft_size = config.get("fft_size", 2048)
    audio_source_cfg = config.get("audio_source", "microphone")
    audio_device = config.get("audio_device")
    audio_monitor_output = config.get("audio_monitor_output")
    audio_pulse_source = config.get("audio_pulse_source")
    if audio_monitor_output:
        monitor_idx = find_monitor_of_output(str(audio_monitor_output))
        if monitor_idx is not None:
            audio_device = monitor_idx
        else:
            print(
                f"Warning: no monitor found for output '{audio_monitor_output}'. "
                "Run --list-devices and look for 'Monitor of ...'. Using audio_device."
            )

    # ResoniteLink port changes each session - prompt if not set
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
    await client.connect()

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

    # Audio source (skip if demo mode)
    audio = None
    chunk_size = fft_size
    if not demo:
        if audio_pulse_source:
            if pulse_source_available():
                audio = PulseSource(str(audio_pulse_source), sample_rate, chunk_size)
            else:
                print("audio_pulse_source is set but 'ffmpeg' not found. Install ffmpeg.")
                await client.teardown()
                await client.disconnect()
                sys.exit(1)
        elif isinstance(audio_source_cfg, str) and audio_source_cfg.lower() == "microphone":
            audio = MicrophoneSource(sample_rate, chunk_size, device=audio_device)
        else:
            audio = FileSource(str(audio_source_cfg), sample_rate, chunk_size)
        try:
            audio.start()
        except Exception as e:
            print(f"Failed to start audio: {e}")
            await client.teardown()
            await client.disconnect()
            sys.exit(1)
        kind = "pulse" if isinstance(audio, PulseSource) else "microphone" if isinstance(audio, MicrophoneSource) else "file"
        print(f"Audio: {kind} ({audio.get_input_description()})")
    else:
        print("Audio: none (demo mode – no music reaction; run without --demo for audio-reactive lights)")

    pattern_engine = PatternEngine(
        layout,
        chase_tail=chase_tail,
        rotation_enabled=rotation_enabled,
        rotation_speed=rotation_speed,
        rotation_audio_boost=rotation_audio_boost,
    )
    interval = 1.0 / update_rate

    print("Running. Press Ctrl+C to stop.")

    try:
        while True:
            loop_start = asyncio.get_running_loop().time()
            if audio:
                samples = audio.read()
                bands = fft_frequency_bands(samples, sample_rate, fft_size)
            else:
                bands = None  # demo: no audio
            states = pattern_engine.compute(pattern, bands)
            await client.update_lights(states)

            elapsed = asyncio.get_running_loop().time() - loop_start
            await asyncio.sleep(max(0, interval - elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        if audio:
            audio.stop()
        await client.teardown()
        await client.disconnect()
        print("Stopped.")


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
    parser = argparse.ArgumentParser(description="Resonite Audio Light Controller")
    parser.add_argument("--config", "-c", help="Config file path")
    parser.add_argument("--pattern", "-p", choices=[p.value for p in Pattern], help="Pattern to run")
    parser.add_argument("--port", type=str, help="ResoniteLink port (skips prompt)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive layout setup")
    parser.add_argument("--demo", action="store_true", help="Run without audio (patterns only)")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio input devices and exit (use with config: audio_device: <index>)",
    )
    parser.add_argument(
        "--list-output-devices",
        action="store_true",
        help="List audio output devices (speakers, DAC, HDMI). To capture from an output, use its monitor in --list-devices.",
    )
    args = parser.parse_args()

    if args.list_output_devices:
        default_idx = get_default_output_device_index()
        default_name = get_default_output_device_name()
        print("Audio output devices (speakers, DAC, HDMI):")
        if default_idx is not None:
            print(f"  Current default: index {default_idx} ({default_name})")
        else:
            print("  Current default: (system default)")
        print()
        for idx, name in list_output_devices():
            mark = "  ← default" if idx == default_idx else ""
            print(f"  {idx}: {name}{mark}")
        print()
        print("To capture from an output, use an INPUT that monitors it (e.g. 'Monitor of ...').")
        print("Run --list-devices to see inputs; set audio_device to the monitor's index.")
        return

    if args.list_devices:
        default_idx = get_default_input_device_index()
        default_name = get_default_input_device_name()
        print("Audio input devices (use audio_device: <index> in config to choose):")
        if default_idx is not None:
            print(f"  Current default: index {default_idx} ({default_name})")
        else:
            print("  Current default: (system default)")
        print()
        for idx, name in list_input_devices():
            mark = "  ← default" if idx == default_idx else ""
            print(f"  {idx}: {name}{mark}")
        return

    config = load_config(args.config)
    layout_override = None
    if args.interactive:
        layout_override = interactive_layout()

    asyncio.run(run(
        config,
        pattern_name=args.pattern,
        layout_override=layout_override,
        demo=args.demo,
        port_override=args.port,
    ))


if __name__ == "__main__":
    main()
