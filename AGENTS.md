# JusAnim agent notes

- 2D engine: `2d/make_story.py` (edit captions in `2d/caps3.txt`)
- Score: `2d/audio.py` → `2d/audio.wav`, deterministic; any rewrite must stay
  byte-identical (`cmp` against the committed wav) — keep float expressions
  verbatim (`0.02+0.1` is NOT `0.12`; same rule for hoisted subexpressions)
- 2D shared lib: `2d/engine.py` — paint ops (sky/hill/disc/ring/line/fade),
  caption filters with automatic font lookup (Fedora/Debian/legacy paths),
  ffmpeg mux with clear errors; selftest: `python3 2d/engine.py`
- Two Moons trilogy: `2d/two_moons{,_2,_3}.py` — story beats only, paint via
  engine; captions embedded as CAPTIONS; render `python3 two_moons.py`,
  full film `python3 two_moons.py --mux out.mp4` (run from `2d/` so
  `audio.wav` sits beside `engine.py`)
- 3D engine: `3d/storyvid.py` — usage: `python3 storyvid.py <script.json> out.mp4`
  (frames render in parallel; `--jobs N`, default min(8, cores))
- Perf policy: vectorize via slices/`translate`, never NumPy (zero-dep identity);
  prove with old-vs-new benchmarks + `cmp`-identical rebuilds (frames 324/300/300)
- Requirements: Python 3.10+, ffmpeg on PATH, a Liberation Sans TTF for captions
- Renders frames as PNG then muxes with ffmpeg; no other deps
- Outputs are gitignored (`j/k/m*.png`, `caps.txt`, `*.mp4` — tracked films
  stay tracked); finished films live on the GitHub release, not in the repo
