<p align="center">
  <img src="docs/logo.png" width="320" alt="JusAnim"/>
</p>

<h1 align="center">JusAnim</h1>

<p align="center">
  <i>Tiny procedural animation library.<br>Pure Python + ffmpeg. No dependencies, no excuses.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="python"/>
  <img src="https://img.shields.io/badge/ffmpeg-required-red" alt="ffmpeg"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license"/>
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="deps"/>
</p>

---

## ✦ What it is

Tiny engines that turn code and JSON scripts into finished short films:

<table>
<tr>
<td width="50%">

### `2d/` — pixel story engine
A grid world where a single pixel paints the universe, plus a shared
paint engine (`engine.py`) behind the Two Moons trilogy. Synthesized score included.

<img src="docs/preview_2d.gif" width="100%"/>

</td>
<td width="50%">

### `3d/` — sphere world engine
Raytraced sphere people on a checkered plane, orbiting cameras, JSON-driven,
frames rendered in parallel across all cores.

<img src="docs/preview_3d.gif" width="100%"/>

</td>
</tr>
</table>

## ✦ Quickstart

```bash
cd 2d
python3 two_moons.py --mux two_moons.mp4   # render + captions + score, one command
cd ../3d
python3 storyvid.py last_pixel_3d.json out.mp4 --jobs 8
```

Every beat of a story is one JSON object:

```json
{ "caption": "Then the Void came.", "white": 0, "void": {"x": 3.0, "r": 1.5}, "hop": true }
```

`x` positions, the void's `{x, r}`, visibility (`null` hides), hop-walk cycles, captions — that's the whole legacy API. The boundless format additionally supports any number of `person`/`sphere`/`box` objects, `camera`/`look` paths, and per-film `settings` (`W`, `H`, `FPS`, `BEAT_FRAMES`) — see the `storyvid.py` header. Tune `--jobs N` to the machine (default: min(8, cores)).

## ✦ The Last Pixel — in both dimensions

| | 2D | 3D |
|---|---|---|
| Engine | `2d/make_story.py` | `3d/storyvid.py` |
| Runtime | 36s | 12s |
| Audio | full score | compressed score |
| Script format | code edit + `caps3.txt` | `last_pixel_3d.json` |

## ✦ Two Moons trilogy

Three short 2D films sharing one engine (`2d/engine.py` — paint ops, caption
filters with automatic font lookup, ffmpeg mux, `python3 2d/engine.py` selftest):

| | Story | Look | Runtime |
|---|---|---|---|
| `2d/two_moons.py` | a spark vs. the Rust | grid garden, glow orbs, shockwave bloom | 32s |
| `2d/two_moons_2.py` | seeds cross five skies | dusk hills, constellations, nebula, rain, dawn | 30s |
| `2d/two_moons_3.py` | seasons turn full circle | trees, falling leaves, snow, twin moons | 30s |

One command each (run from `2d/`, needs `audio.wav` beside `engine.py`):

```bash
python3 two_moons.py --mux two_moons.mp4
```

Without `--mux` it only renders the numbered frames.

## ✦ Performance

Zero dependencies doesn't mean slow. Hot pixel ops are vectorized C-level
fills (`bytes.translate` fades, per-chord disc slices), the score renders in
~2s, and 3D frames go through a process pool — the whole trilogy rebuilds in
about 12 seconds. Every optimization is verified byte-identical against the
previous output (`cmp` the WAV/mp4), so faster never means different.

## ✦ Videos

Rendered frames, caption filters, and mp4s are gitignored build outputs —
reproduce any film with its one-command build above.
All finished renders attached to the [v1.0 release](https://github.com/shubh72010/JusAnim/releases/tag/v1.0).

## ✦ Roadmap

- [ ] more actors, colors, and cameras in the 3D engine
- [ ] a proper scene DSL parsing scenes → JSON
- [ ] sprite shapes (squares, triangles) in the 2D engine
- [ ] audio narration

---

<p align="center"><i>Maybe the world just needs a fresh start.</i></p>
