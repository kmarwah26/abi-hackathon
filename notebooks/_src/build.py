"""Build .ipynb files from plain-text cell-marked source files (in this dir).

Markers, each on its own line:
    @@@MD      -> start a markdown cell
    @@@CODE    -> start a code cell
Inside a markdown cell, a line of the form
    @@@IMG:key[:width]
is replaced by an inlined base64 SVG <img> from diagrams.DIAGRAMS[key].

Outputs <name>.ipynb to the PARENT directory (notebooks/).
Run: python3 _src/build.py   (from notebooks/)  or  python3 build.py (from _src/)
"""
import base64
import glob
import json
import os

import diagrams

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)  # notebooks/


def img_tag(key, width=820):
    svg = diagrams.DIAGRAMS[key]()
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<img src="data:image/svg+xml;base64,{b64}" '
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
