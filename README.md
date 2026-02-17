# Resonite Light Controller (pattern-only)

Creates and controls FrooxEngine.Light components in Resonite via [ResoniteLink](https://github.com/Yellow-Dog-Man/ResoniteLink). Pick a pattern, lights run in real time. **No audio capture** – patterns use time-based animation only.

---

## ⚠️ IN DEVELOPMENT ⚠️

Linux-only tested. Windows/macOS untested.

---

## What does this do?

The program creates lights in Resonite, one per zone (left, right, front, back, top), and drives them with patterns. You pick an initial pattern, then **switch patterns live** by typing a number (1–18) + Enter.

**Keyboard switching**

| Keys   | Pattern        | Keys   | Pattern      |
|--------|----------------|--------|--------------|
| 1+Enter| chase          | 10+Enter| upper_bass   |
| 2+Enter| chase_reverse  | 11+Enter| bass_flood   |
| 3+Enter| swirl          | 12+Enter| treble_hue   |
| 4+Enter| front_to_back  | 13+Enter| band_split   |
| 5+Enter| back_to_front  | 14+Enter| music_color  |
| 6+Enter| left_off       | 15+Enter| breathing    |
| 7+Enter| right_off      | 16+Enter| all_on       |
| 8+Enter| left_right_alt | 17+Enter| zone_mix     |
| 9+Enter| center_out     | 18+Enter| beat_hue     |

**Ctrl+C** – Stops the app and cleans up (removes lights from world). Does not hang.

## Setup

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Enable ResoniteLink in Resonite**  
   Host a world, enable ResoniteLink, note the port.

3. **Run**

   ```bash
   python main.py
   ```

## Usage

```bash
# Run (prompts for ResoniteLink port)
python main.py

# Initial pattern
python main.py -p chase
python main.py -p zone_mix

# Skip port prompt
python main.py --port 27404

# Interactive layout
python main.py -i
```

## Config (optional)

| Option | Description |
|--------|--------------|
| `resonite_port` | ResoniteLink port |
| `parent_slot_id` | Slot to parent lights under |
| `center` | `{x, y, z}` offset |
| `layout` | `left`, `right`, `front`, `back`, `top`, `bottom` counts |
| `default_pattern` | Initial pattern |
| `chase_tail` | Chase tail length |
| `update_rate` | Updates per second (default 30) |

## Patterns

| Pattern | Description |
|---------|-------------|
| `chase` / `chase_reverse` | Moving head with tail |
| `swirl` | Circular rotating chase |
| `front_to_back` / `back_to_front` | Wave across zones |
| `left_off` / `right_off` | Half room on, half off |
| `left_right_alt` | Left and right alternate |
| `center_out` | Middle lights first, expand outward |
| `upper_bass`, `bass_flood`, `treble_hue`, `band_split` | (No audio – use time-based fallback) |
| `music_color`, `breathing`, `all_on` | Static / slow color shift |
| `zone_mix` | Different pattern per zone, cycles every 14s |
| `beat_hue` | Hue jumps (no beat detection without audio) |
