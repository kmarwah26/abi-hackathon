"""Build .ipynb files from plain-text cell-marked source files (in this dir).

Markers, each on its own line:
    @@@MD      -> start a markdown cell
    @@@CODE    -> start a code cell
Inside a markdown cell, a line of the form
    @@@IMG:key[:width]
is replaced by an inlined base64 <img> from diagrams.DIAGRAMS[key]. The SVG is
RASTERIZED TO PNG at build time and embedded as a PNG data URI, because Databricks'
markdown sanitizer does NOT render SVG data URIs (it does render PNG ones). If a
rasterizer isn't available (e.g. building off macOS), it falls back to inline SVG.

Outputs <name>.ipynb to the PARENT directory (notebooks/).
Run: python3 _src/build.py   (from notebooks/)  or  python3 build.py (from _src/)
"""
import base64
import glob
import io
import json
import os
import re
import subprocess
import tempfile

import diagrams

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)  # notebooks/

_PNG_CACHE = {}   # key -> data-URI string (rasterize each diagram once)


def _svg_dims(svg):
    w = float(re.search(r'width="([\d.]+)"', svg).group(1))
    h = float(re.search(r'height="([\d.]+)"', svg).group(1))
    return w, h


def _rasterize_png(svg, scale=2, pad=10):
    """SVG string -> PNG bytes, via macOS `qlmanage` + a tight Pillow auto-crop.
    Raises if qlmanage/Pillow aren't available so the caller can fall back to SVG."""
    from PIL import Image, ImageChops  # local import so the SVG fallback needs no Pillow
    w, h = _svg_dims(svg)
    with tempfile.TemporaryDirectory() as d:
        svg_path = os.path.join(d, "d.svg")
        with open(svg_path, "w") as f:
            f.write(svg)
        size = int(max(w, h) * scale)  # 2x the long side → retina-crisp
        subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", d, svg_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        png_path = svg_path + ".png"           # qlmanage appends .png to the filename
        if not os.path.exists(png_path):
            raise RuntimeError("qlmanage produced no PNG")
        img = Image.open(png_path).convert("RGBA")
        # Flatten onto white, then auto-crop qlmanage's square padding to the content.
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        rgb = bg.convert("RGB")
        bbox = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).getbbox()
        if bbox:
            l, t, r, b = bbox
            rgb = rgb.crop((max(0, l - pad), max(0, t - pad),
                            min(rgb.width, r + pad), min(rgb.height, b + pad)))
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue()


def img_tag(key, width=820):
    if key not in _PNG_CACHE:
        svg = diagrams.DIAGRAMS[key]()
        try:
            png = _rasterize_png(svg)
            _PNG_CACHE[key] = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        except Exception as e:  # noqa: BLE001 — rasterizer missing → keep SVG so build still works
            print(f"  (rasterize failed for {key}: {type(e).__name__}; embedding SVG) ")
            b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            _PNG_CACHE[key] = "data:image/svg+xml;base64," + b64
    return (f'<img src="{_PNG_CACHE[key]}" '
            f'width="{width}" alt="{key}" style="max-width:100%;height:auto;"/>')


def expand_images(text):
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("@@@IMG:"):
            parts = s[len("@@@IMG:"):].split(":")
            key = parts[0]
            width = int(parts[1]) if len(parts) > 1 else 820
            out.append(img_tag(key, width))
        else:
            out.append(line)
    return "\n".join(out)


def parse(path):
    with open(path) as f:
        lines = f.read().split("\n")
    cells, cur_type, cur = [], None, []

    def flush():
        if cur_type is None:
            return
        src = "\n".join(cur).strip("\n")
        if cur_type == "markdown":
            src = expand_images(src)
            cells.append({"cell_type": "markdown", "metadata": {},
                          "source": src.splitlines(keepends=True) or [""]})
        else:
            cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                          "outputs": [], "source": src.splitlines(keepends=True) or [""]})

    for ln in lines:
        if ln.strip() == "@@@MD":
            flush(); cur_type, cur = "markdown", []
        elif ln.strip() == "@@@CODE":
            flush(); cur_type, cur = "code", []
        else:
            cur.append(ln)
    flush()
    return cells


def build(src_path):
    cells = parse(src_path)
    nb = {"cells": cells,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    name = os.path.basename(src_path).replace(".nbsrc", ".ipynb")
    out = os.path.join(OUT_DIR, name)
    with open(out, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"wrote {out} ({len(cells)} cells)")


if __name__ == "__main__":
    for p in sorted(glob.glob(os.path.join(HERE, "*.nbsrc"))):
        build(p)
