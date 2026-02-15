# Resonite Audio Light Controller

Audio-reactive lighting for Resonite VR. Uses [ResoniteLink](https://github.com/Yellow-Dog-Man/ResoniteLink) to create and control FrooxEngine.Light components in real time. Define how many lights you want in each direction (left, right, front, back, top), and the program creates them in-world and drives them with patterns that react to music.

---

## ⚠️ IN DEVELOPMENT ⚠️

Linux-only tested. Windows/macOS untested. Some features may not work correctly.

---

## What does this do?

The program captures audio, runs an FFT to get frequency bands (bass, mids, treble), and sends Color/Intensity updates to lights in Resonite over WebSocket. You choose a layout (e.g. 5 left, 5 right, 3 front), pick a pattern (chase, swirl, breathing, etc.), and the lights react in real time.

**Audio sources**

| Source | How it works |
|--------|--------------|
| **Microphone** | Default. Captures from your default recording device. |
| **System audio / Spotify** | Route your output into a virtual input. Then use mic mode. Linux: PulseAudio monitor. Windows: Stereo Mix or VB-Audio Cable. macOS: BlackHole. |
| **Audio file** | Set `audio_source: /path/to/file.wav` in optional config. Supports WAV/FLAC. Loops. |

**You don't need the Resonance mod** – This program does its own FFT on mic or file input and sends light updates via ResoniteLink. [Resonance](https://github.com/BlueCyro/Resonance) is different: it runs FFT inside Resonite. We drive the lights directly.

## Features

- **Layout by zone** – Specify light counts per direction (e.g. 5 left, 5 right, 3 front, 2 back, 4 top) via config or `-i` interactive prompt
- **Patterns** – Chase (with tail), front-to-back wave, left-off (left dark, right on), music-color (all on, color from audio), all-on
- **Audio-reactive** – FFT on mic or audio file; bass drives intensity, mids/treble drive hue
- **ResoniteLink** – Creates PointLights in Resonite via WebSocket and updates Color/Intensity in real time

## Setup

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Bash/Zsh; Fish: source .venv/bin/activate.fish
   pip install -r requirements.txt
   ```
   Or without activating: `.venv/bin/pip install -r requirements.txt` then run with `.venv/bin/python main.py`.

2. **Enable ResoniteLink in Resonite**  
   In Resonite, host a world and enable ResoniteLink. Note the port (changes each session).

3. **Run** – No config required. The program asks for the ResoniteLink port when you start. See [docs/TESTING.md](docs/TESTING.md) for first-run steps (venv, Arch deps).

## Usage

```bash
# Run with audio (prompts for ResoniteLink port)
python main.py

# Demo mode (no audio, patterns only)
python main.py --demo

# Specific pattern: -p <name>  (see Patterns section below)
python main.py -p chase
python main.py -p zone_mix

# Skip port prompt
python main.py --port 27404

# Interactive layout (prompt for light counts per zone)
python main.py -i

# List audio input devices
python main.py --list-devices
```

## Config (optional)

Copy `config.example.yaml` to `config.yaml` only if you want to customize. Defaults work without it.

| Option | Description |
|--------|--------------|
| `resonite_port` | ResoniteLink port (optional; prompted at startup if unset; or use `--port`) |
| `parent_slot_id` | Slot ID to parent lights under (e.g. DJ booth). Omit for Root. |
| `center` | `{x, y, z}` offset for all light positions (e.g. around DJ booth) |
| `rotation_enabled` | Spin lights around Y axis (experimental, may not work) |
| `rotation_speed` | Degrees per second (default 30) |
| `rotation_audio_boost` | Boost rotation speed with bass |
| `audio_source` | `speakers` (system output), `microphone`, or path to audio file |
| `audio_device` | Optional: input device index or name (run `--list-devices` to see options) |
| `layout` | `left`, `right`, `front`, `back`, `top`, `bottom` counts |
| `default_pattern` | Pattern to run |
| `chase_tail` | Number of lights in chase tail (2–3) |
| `update_rate` | Updates per second (default 30) |

## Patterns

| Pattern | Description |
|---------|-------------|
| `chase` / `chase_reverse` | Moving head with tail, optionally reversed |
| `swirl` | Circular rotating chase, speed boosted by upper bass |
| `upper_bass` | All lights pulse with 60–150 Hz (punch/kick) |
| `bass_flood` | Low freq drives brightness (flood lights) |
| `treble_hue` | High freq drives hue, overall drives intensity |
| `band_split` | Bass→intensity, treble→hue (classic DMX-style mapping) |
| `breathing` | Locked color, subtle hue shift, soft intensity pulse |
| `all_on` | All lights fully on (no audio reaction) |
| `music_color` | All on, color from spectrum |
| `front_to_back` / `back_to_front` | Wave across zones |
| `left_off` / `right_off` | Half room on, half off |
| `left_right_alt` | Left and right zones alternate pulsing |
| `center_out` | Within each zone: middle lights first, expand outward (great for top rows) |
| `zone_mix` | Different pattern per zone; cycles through sets every 14s (top=chase, left=off, etc.) |
| `beat_hue` | Hue jumps on beat detection (bass spike); intensity pulses with bass |

## Implementation Notes

- **Light component**: Uses `[FrooxEngine]FrooxEngine.Light` with `LightType=0` (Point). Color is `colorX` (r,g,b,a) per ResoniteLink.
- **DynamicVariableSpace**: Each session creates an `AudioLights` space for organization; lights are named `Light_{zone}_{index}`.
- **Positioning**: Use `parent_slot_id` to place lights under a DJ booth; use `center` to offset all zones.
