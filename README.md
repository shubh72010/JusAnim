# JusAnim

Tiny procedural animation library. Zero dependencies beyond Python + ffmpeg.

## Layout

- `2d/` — grid-world pixel story engine (`make_story.py`), synthesized score (`audio.py`), captions track, finished film `the_last_pixel.mp4`
- `3d/` — sphere-world raytraced engine (`storyvid.py`), JSON-driven scripts

## 3D usage

```
cd 3d
python3 storyvid.py last_pixel_3d.json out.mp4
```

Each beat: `{"caption": "...", "white": x|null, "red": x|null, "blue": x|null, "void": {"x": x, "r": r}|null, "hop": true|false}`

## 2D usage

```
cd 2d
python3 make_story.py   # renders frames (edit OUT for output dir)
```

## Videos

All finished renders are attached to the v1.0 release:
https://github.com/shubh72010/JusAnim/releases/tag/v1.0
