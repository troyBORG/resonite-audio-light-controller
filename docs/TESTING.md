# Testing the Resonite Audio Light Controller

## 1. Setup (Arch Linux)

Create a virtual environment and install dependencies:

```bash
cd /mnt/12tb/git/resonite-audio-light-controller

# Create venv
python -m venv .venv

# Activate (run this in each new terminal)
source .venv/bin/activate

# Install deps (Arch may need: pacman -S portaudio libsndfile)
pip install -r requirements.txt
```

## 2. Start Resonite First

1. Launch Resonite
2. Create or join a world (you must be the **host** to use ResoniteLink)
3. Enable ResoniteLink in settings
4. Note the port shown (e.g. `27404`)

## 3. Run the Controller

```bash
# Activate venv if needed
source .venv/bin/activate

# Demo mode (no audio) - best first test
python main.py --demo -p chase
```

When prompted, enter the ResoniteLink port (e.g. `27404`).

## 4. What Should Happen

- Lights appear in your Resonite world (5 left, 5 right, 3 front, 2 back, 4 top by default)
- Chase pattern runs (moving lit head with tail)
- Press Ctrl+C to stop and remove lights

## 5. With Audio

```bash
python main.py -p chase
```

Uses your default microphone. Route system audio to a virtual input if you want Spotify/music.

## Troubleshooting

| Problem | Check |
|---------|-------|
| Connection refused | Resonite running? In a world? ResoniteLink enabled? Correct port? |
| ModuleNotFoundError | `pip install -r requirements.txt` inside the venv |
| sounddevice / portaudio error | `sudo pacman -S portaudio` |
| soundfile / libsndfile error | `sudo pacman -S libsndfile` |
