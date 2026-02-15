# Testing the Resonite Audio Light Controller

## 1. Setup (Arch Linux)

Create a virtual environment and install dependencies. **Use your system Python** (e.g. from pacman), not an IDE/Cursor Python, or the venv can end up broken.

```bash
cd resonite-audio-light-controller

# Remove old venv if you had one
rm -rf .venv

# Create venv with system Python (Arch)
/usr/bin/python -m venv .venv
# or:  /usr/bin/python3 -m venv .venv

# Install deps (Arch may need: pacman -S portaudio libsndfile)
.venv/bin/pip install -r requirements.txt
```

Run the app with the venv Python (no need to "activate" in Fish):

```bash
.venv/bin/python main.py --demo -p chase
```

**Fish users:** Run each command above on its own line. Do not paste the whole block. If you prefer to activate: `source .venv/bin/activate.fish`, then `pip install -r requirements.txt` and `python main.py ...`.

## 2. Start Resonite First

1. Launch Resonite
2. Create or join a world (you must be the **host** to use ResoniteLink)
3. Enable ResoniteLink in settings
4. Note the port shown (e.g. `27404`)

## 3. Run the Controller

```bash
# If you activated the venv (Bash/Zsh/Fish):
python main.py --demo -p chase

# If you didn't activate (Option C), use the venv Python:
.venv/bin/python main.py --demo -p chase
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
