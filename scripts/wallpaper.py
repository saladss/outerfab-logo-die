#!/usr/bin/env python3
"""Tile a houndstooth "wallpaper" onto Metal5 wherever the routed chip has nothing.

Run after the chip flow, before the precheck:

    python3 scripts/wallpaper.py final/gds/chip_top.gds final/gds/chip_top_wallpaper.gds

The pattern is the real houndstooth weave: a 2/2 twill with 4 dark / 4 light threads in
warp and weft (8x8 threads per repeat).  Each thread crossing becomes a square; crossings
that touch a diagonal neighbour only at a corner get a 45-degree chamfer so no two shapes
meet corner-to-corner.  Keep-outs (art macros + border, other macros, anything already on
Metal5) are expanded to whole threads, so clipping never leaves slivers.  Floating top
metal is treated exactly like the logo and the wafer.space ID cells.
"""
import argparse
import re
import klayout.db as db

GRID = 5


def snap(nm):
    return int(round(nm / GRID)) * GRID


def houndstooth_dark(i, j):
    """True if thread crossing (i, j) shows dark. i: warp index (x), j: weft index (y)."""
    warp_over = (i + j) % 4 < 2          # 2/2 twill
    warp_dark = (i % 8) < 4
    weft_dark = (j % 8) < 4
    return warp_dark if warp_over else weft_dark


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--top", default="chip_top")
    ap.add_argument("--layer", default="81/0", help="Metal5")
    ap.add_argument("--tile", type=float, default=160, help="repeat length in um (8 threads)")
    ap.add_argument("--core", type=float, nargs=4, default=[442, 442, 3490, 2089], metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--core-margin", type=float, default=30, help="stay this far inside the core (um)")
    ap.add_argument("--art", default=r"outerfab_logo|portrait_.*", help="regex of art cells to keep a border around")
    ap.add_argument("--art-border", type=float, default=150, help="clear border around art cells (um)")
    ap.add_argument("--macro-border", type=float, default=20, help="clear border around every other macro (um)")
    ap.add_argument("--m5-space", type=float, default=1.0, help="clearance to existing Metal5 (um)")
    ap.add_argument("--chamfer", type=float, default=1.0, help="45-degree chamfer leg at diagonal contacts (um)")
    ap.add_argument("--gap", type=float, default=0.0, help="optional gap between all threads (um); 0 = merged")
    ap.add_argument("--partial", action="store_true", help="allow partial repeats (default: only whole 8x8-thread tiles)")
    a = ap.parse_args()

    ly = db.Layout()
    ly.read(a.inp)
    top = ly.cell(a.top)
    assert top is not None, f"top cell {a.top} not found"
    l, dt = map(int, a.layer.split("/"))
    m5 = ly.layer(l, dt)

    # --- keep-outs ---------------------------------------------------------------------
    keep = db.Region()
    art_re = re.compile(a.art)
    for inst in top.each_inst():
        bb = inst.bbox()
        border = a.art_border if art_re.fullmatch(inst.cell.name) else a.macro_border
        keep.insert(bb.enlarged(snap(border * 1000), snap(border * 1000)))
    existing = db.Region(top.begin_shapes_rec(m5))
    keep += existing.sized(snap(a.m5_space * 1000))
    keep.merge()

    # --- thread grid -----------------------------------------------------------------
    t = snap(a.tile / 8 * 1000)                       # thread pitch in nm
    x0 = snap((a.core[0] + a.core_margin) * 1000)
    y0 = snap((a.core[1] + a.core_margin) * 1000)
    x1 = snap((a.core[2] - a.core_margin) * 1000)
    y1 = snap((a.core[3] - a.core_margin) * 1000)
    ni = (x1 - x0) // t
    nj = (y1 - y0) // t
    if not a.partial:  # centre whole repeats within the core
        ni, nj = ni // 8 * 8, nj // 8 * 8
        x0 = snap(x0 + ((x1 - x0) - ni * t) / 2)
        y0 = snap(y0 + ((y1 - y0) - nj * t) / 2)

    allowed = db.Region(db.Box(x0, y0, x0 + ni * t, y0 + nj * t)) - keep
    # a thread is usable only if its whole square (or, by default, its whole 8x8 repeat)
    # lies in the allowed region
    usable = [[False] * nj for _ in range(ni)]
    step = 1 if a.partial else 8
    for i in range(0, ni - step + 1, step):
        for j in range(0, nj - step + 1, step):
            b = db.Box(x0 + i * t, y0 + j * t, x0 + (i + step) * t, y0 + (j + step) * t)
            if (db.Region(b) - allowed).is_empty():
                for ii in range(i, i + step):
                    for jj in range(j, j + step):
                        usable[ii][jj] = True

    dark = [[usable[i][j] and houndstooth_dark(i, j) for j in range(nj)] for i in range(ni)]

    def d(i, j):
        return 0 <= i < ni and 0 <= j < nj and dark[i][j]

    c = snap(a.chamfer * 1000)
    g = snap(a.gap / 2 * 1000)
    out = db.Region()
    for i in range(ni):
        for j in range(nj):
            if not dark[i][j]:
                continue
            xl, yb = x0 + i * t + g, y0 + j * t + g
            xr, yt = x0 + (i + 1) * t - g, y0 + (j + 1) * t - g
            # corners to chamfer: diagonal neighbour dark, both orthogonal neighbours light
            cut_bl = d(i - 1, j - 1) and not d(i - 1, j) and not d(i, j - 1)
            cut_br = d(i + 1, j - 1) and not d(i + 1, j) and not d(i, j - 1)
            cut_tr = d(i + 1, j + 1) and not d(i + 1, j) and not d(i, j + 1)
            cut_tl = d(i - 1, j + 1) and not d(i - 1, j) and not d(i, j + 1)
            pts = []
            pts += [db.Point(xl + c, yb), db.Point(xl, yb + c)] if cut_bl else [db.Point(xl, yb)]
            pts += [db.Point(xl, yt - c), db.Point(xl + c, yt)] if cut_tl else [db.Point(xl, yt)]
            pts += [db.Point(xr - c, yt), db.Point(xr, yt - c)] if cut_tr else [db.Point(xr, yt)]
            pts += [db.Point(xr, yb + c), db.Point(xr - c, yb)] if cut_br else [db.Point(xr, yb)]
            out.insert(db.Polygon(pts))
    out.merge()

    # --- sanity ------------------------------------------------------------------------
    for p in out.each():
        for pt in p.each_point_hull():
            assert pt.x % GRID == 0 and pt.y % GRID == 0, "off-grid vertex"
        for e in p.each_edge():
            dx, dy = abs(e.dx()), abs(e.dy())
            assert dx == 0 or dy == 0 or dx == dy, "non-45 edge"
    assert (out & keep).is_empty(), "pattern overlaps a keep-out"

    top.shapes(m5).insert(out)
    ly.write(a.out)
    core_area = (a.core[2] - a.core[0]) * (a.core[3] - a.core[1])
    print(f"{a.out}: {out.count()} houndstooth polygons on {a.layer}, "
          f"{out.area() * 1e-6 / core_area * 100:.1f}% of core area; "
          f"M5 total now {(existing + out).merged().area() * 1e-6 / core_area * 100:.1f}% of core")


if __name__ == "__main__":
    main()
