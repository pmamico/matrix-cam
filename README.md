# Matrix Camera

> Warning: may contains glitches 👾

ASCII camera viewer for macOS terminals. 
The application captures BGR frames from the webcam, maps each pixel to ASCII characters, and renders the result using bright green Matrix-style glyphs.

## Requirements

- Python 3.11+
- macOS terminal (Terminal.app or iTerm2)
- Camera permission granted to the terminal you run the app from

## Installation


### homebrew 
```shell
brew install pmamico/keg/matrix-cam
```

### from source

```bash
git clone https://github.com/pmamico/homebrew-keg.git
cd homebrew-keg
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

```bash
matrix-cam 
```

## Running the Prototype

Start with the one-frame prototype to validate camera access without curses:

```bash
python -m matrix_cam.prototype [--stats] [--save-frame frame.png] [--no-color]
```

Useful flags:

- `--stats`: print captured frame shape, min/max, mean, and standard deviation for quick intensity checks.
- `--save-frame frame.png`: save the raw BGR frame as PNG for later inspection.
- `--no-color`: disable the ANSI green wrapper for plain ASCII output (suitable for piping).
- `--segment`: compute a foreground mask and blank out the background before rendering.
- `--segment-backend {mog2,selfie}`: pick the segmentation backend. `selfie` requires MediaPipe (`pip install 'matrix-cam[ml]'`).
- `--segment-confidence`: control the mask confidence threshold used by ML backends (default 0.3).

## Full-Screen UI

```bash
matrix-cam  # or: python -m matrix_cam.main
```

Run `matrix-cam --help` to list the available CLI options (refresh delay, segmentation backend, camera source, mask toggle). For example, `matrix-cam --source 1` starts the UI using camera index 1.

Key bindings:

- `q`: quit
- `f`: toggle foreground masking (masking is enabled by default)
- `b`: cycle brightness levels (25/50/75/100%)
- `g`: toggle glitch effects

The UI auto-resizes to the terminal window, renders live ASCII frames in full screen, and displays status information (resolution, errors, mask coverage) in the bottom bar. If the terminal is smaller than 40×12 cells, a warning message appears instead of the feed.

> Tip: the camera discards ~10 warmup frames on startup. In very dark rooms the first captured frames can be black; if the preview stays black, re-check macOS camera permissions.

## Tests

```bash
pytest
```

## Foreground Segmentation

- MOG2 background subtraction (OpenCV) is the default backend because it is fast and has zero extra dependencies.
- In the curses UI, `f` toggles masking and the status bar shows the backend name plus estimated foreground coverage.
- The optional `selfie` backend relies on MediaPipe Selfie Segmentation. Install it via `pip install 'matrix-cam[ml]'`. When unavailable, the app falls back to MOG2 and shows a descriptive error.
- The ASCII renderer replaces any background cell with a space character, preserving row length so curses padding stays stable even when backgrounds vanish.

## macOS Camera Permission

The first launch from Terminal/iTerm2 might not have camera access yet. If you see a black window or “Unable to open camera” errors:

1. Open macOS **System Settings**.
2. Navigate to **Privacy & Security → Camera** and enable the terminal application you use.
3. Restart the terminal and run the program again.
