# Resonite Audio Light Controller

Audio-reactive lighting for Resonite VR. Uses [ResoniteLink](https://github.com/Yellow-Dog-Man/ResoniteLink) to create and control FrooxEngine.Light components in real time. Define how many lights you want in each direction (left, right, front, back, top), and the program creates them in-world and drives them with patterns that react to music.

## What does this do?

The program captures audio, runs an FFT to get frequency bands (bass, mids, treble), and sends Color/Intensity updates to lights in Resonite over WebSocket. You choose a layout (e.g. 5 left, 5 right, 3 front), pick a pattern (chase, swirl, breathing, etc.), and the lights react in real time.

**Audio sources**

| Source | How it works |
|--------|--------------|
| **Microphone** | Default. Captures from your default recording device. |
| **System audio / Spotify** | Route your output into a virtual input. Then use mic mode. Linux: PulseAudio monitor. Windows: Stereo Mix or VB-Audio Cable. macOS: BlackHole. |
| **Audio file** | Set `audio_source: /path/to/file.wav` in config. Supports WAV/FLAC. Loops. |

**Resonance mod** – [Resonance](https://github.com/BlueCyro/Resonance) does FFT inside Resonite on audio streams. A future mode could read its band values instead of capturing audio externally. For now, use mic or file.

## Features

- **Layout by zone** – Specify light counts per direction (e.g. 5 left, 5 right, 3 front, 2 back, 4 top)
- **Patterns** – Chase (with tail), front-to-back wave, left-off (left dark, right on), music-color (all on, color from audio), all-on
- **Audio-reactive** – FFT on mic or audio file; bass drives intensity, mids/treble drive hue
- **ResoniteLink** – Creates PointLights in Resonite via WebSocket and updates Color/Intensity in real time

## Setup

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **Enable ResoniteLink in Resonite**  
   In Resonite, enable the ResoniteLink WebSocket server (typically `ws://localhost:27404/ResoniteLink`).

3. **Configure**

   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml: layout, audio_source, resonite_url
   ```

## Usage

```bash
# Run with config file
python main.py

# Interactive layout (prompt for light counts)
python main.py -i

# Specific pattern
python main.py -p chase
python main.py -p chase_reverse
python main.py -p swirl
python main.py -p front_to_back
python main.py -p back_to_front
python main.py -p left_off
python main.py -p right_off
python main.py -p upper_bass
python main.py -p music_color
python main.py -p breathing
python main.py -p all_on

# Demo mode (no audio, patterns only)
python main.py --demo
```

## Config

| Option        | Description                          |
|---------------|--------------------------------------|
| `resonite_url`| ResoniteLink WebSocket URL           |
| `audio_source`| `microphone` or path to audio file   |
| `layout`      | `left`, `right`, `front`, `back`, `top`, `bottom` counts |
| `default_pattern` | Pattern to run                  |
| `chase_tail`  | Number of lights in chase tail (2–3) |
| `update_rate` | Updates per second (default 30)      |

## Patterns

| Pattern | Description |
|---------|-------------|
| `chase` / `chase_reverse` | Moving head with tail, optionally reversed |
| `swirl` | Circular rotating chase, speed boosted by upper bass |
| `upper_bass` | All lights pulse with 60–150 Hz (punch/kick) |
| `breathing` | Locked color, subtle hue shift, soft intensity pulse |
| `music_color` | All on, color from spectrum |
| `front_to_back` / `back_to_front` | Wave across zones |
| `left_off` / `right_off` | Half room on, half off |

## Implementation Notes

- **Light component**: Uses `[FrooxEngine]FrooxEngine.Light` with `LightType=0` (Point). Color is `colorX` (r,g,b,a) per ResoniteLink.
- **DynamicVariableSpace**: Each session creates an `AudioLights` space for organization; lights are named `Light_{zone}_{index}`.
