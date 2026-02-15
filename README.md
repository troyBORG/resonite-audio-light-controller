# Resonite Audio Light Controller

Audio-reactive lighting for Resonite VR. Define how many lights you want in each direction (left, right, front, back, top), and the program creates them in-world and drives them with patterns that react to music.

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
python main.py -p front_to_back
python main.py -p left_off
python main.py -p music_color
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
