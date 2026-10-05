# JusAnim agent notes

- 2D engine: `2d/make_story.py` (edit captions in `2d/caps3.txt`, score via `2d/audio.py`)
- 3D engine: `3d/storyvid.py` — usage: `python3 storyvid.py <script.json> out.mp4`
- Requirements: Python 3.10+, ffmpeg on PATH, a Liberation Sans TTF for captions
- Renders frames as PNG then muxes with ffmpeg; no other deps
