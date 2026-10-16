#!/usr/bin/env python3
"""Render a logo as chirped diffraction gratings in GDS.

The logo silhouette (SVG) is filled with constant-width metal lines whose pitch
sweeps linearly along a "gradient" direction, so the diffracted colour changes
across the shape under directional light.  Two groups are supported:

* the *wordmark* group gets horizontal lines, pitch sweeping top -> bottom;
* the *mark* group (ring + square) gets lines at -45 degrees, pitch sweeping along
  the +45 degree diagonal (lower-left of the ring -> the square).

Everything is built on a Manhattan 5 nm grid.  The diagonal group is built in a
rotated frame and mapped through the integer matrix (u,v) -> (u+v, v-u), which
turns horizontal edges into exact 45-degree edges while keeping every vertex on
grid - the two things the GF180 geometry deck checks (geom.drc: ongrid(0.005),
angles in {0,45,90,-45}).

Inspired by Tholin's palette_1 test structures (AvalonSemiconductors/ws-submission-2026).
"""
import argparse
import io
import math
import xml.etree.ElementTree as ET

import cairosvg
import numpy as np
import klayout.db as db
from PIL import Image

GRID = 5  # nm; GF180 manufacturing grid


def snap(nm):
    return int(round(nm / GRID)) * GRID


def svg_subset(path, keep):
    """Return SVG text containing only the top-level children with indices in `keep`."""
    tree = ET.parse(path)
    root = tree.getroot()
    children = list(root)
    for i, ch in enumerate(children):
        if i not in keep:
            root.remove(ch)
    return ET.tostring(root)


def rasterise(svg_bytes, w):
    png = cairosvg.svg2png(bytestring=svg_bytes, output_width=w, background_color="white")
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    bg = Image.new("RGBA", img.size, "WHITE")
    bg.paste(img, (0, 0), img)
    return bg.convert("L").point(lambda v: 0 if v > 128 else 255)  # dark -> 255


def bitmap_to_region(bw, px_um):
    """Manhattan Region from a PIL 'L' bitmap (non-zero = ink); y flipped so row 0 is the top."""
    reg = db.Region()
    H, Wd = bw.height, bw.width
    a = np.array(bw) > 0
    s = snap(px_um * 1000)
    for y in range(H):
        row = a[y]
        x = 0
        while x < Wd:
            if row[x]:
                x0 = x
                while x < Wd and row[x]:
                    x += 1
                reg.insert(db.Box(x0 * s, (H - y - 1) * s, x * s, (H - y) * s))
            else:
                x += 1
    reg.merge()
    return reg


def horizontal_grating(x0, x1, y_lo, y_hi, line_w, p_top, p_bot):
    """Horizontal lines between y_lo..y_hi (nm); pitch sweeps p_top (at y_hi) -> p_bot (at y_lo)."""
    reg = db.Region()
    lw = snap(line_w * 1000)
    y = y_hi
    n = 0
    while y - lw >= y_lo:
        frac = (y_hi - y) / (y_hi - y_lo)
        p = p_top + (p_bot - p_top) * frac
        reg.insert(db.Box(x0, y - lw, x1, y))
        y = snap(y - p * 1000)
        n += 1
    return reg, n


def clean(reg, min_feature_um, min_area_um2):
    d = snap(min_feature_um / 2 * 1000)
    reg = reg.merged().sized(-d).sized(d).merged()        # opening: kills slivers thinner than min_feature
    return reg.with_area(round(min_area_um2 * 1e6), None, False)


def diagonal_grating_region(mark_bits, px_um, line_w, p_far, p_near, min_feature, min_area):
    """Lines at -45 deg clipped to the mark, pitch sweeping along +45 deg.

    mark_bits: bool array (rows top->bottom) of the mark on the real-frame raster, px_um per pixel,
    pixel (0,0) at the top-left of the cell.
    Rotated frame (u,v): real = (u+v, v-u); inverse u = (x-y)/2, v = (x+y)/2.  The map scales
    lengths by sqrt(2), so widths/pitches are divided by sqrt(2) in the rotated frame.  v grows
    towards the upper-right: pitch is p_far at min v (lower-left) and p_near at max v (square)."""
    r2 = math.sqrt(2)
    rh, rw = mark_bits.shape
    rs = snap(px_um * 1000)
    ys, xs = np.nonzero(mark_bits)
    if len(xs) == 0:
        return db.Region(), 0
    # real-frame bbox of the ink (nm); y flipped
    xl, xr = xs.min() * rs, (xs.max() + 1) * rs
    yb, yt = (rh - ys.max() - 1) * rs, (rh - ys.min()) * rs
    corners = [(xl, yb), (xr, yb), (xl, yt), (xr, yt)]
    u0 = snap(min((x - y) / 2 for x, y in corners)) - 2000
    u1 = snap(max((x - y) / 2 for x, y in corners)) + 2000
    v0 = snap(min((x + y) / 2 for x, y in corners)) - 2000
    v1 = snap(max((x + y) / 2 for x, y in corners)) + 2000

    s = snap(px_um / r2 * 1000)            # rotated-frame pixel (nm) -> diamond of side px_um
    nu, nv = (u1 - u0) // s, (v1 - v0) // s
    uu = u0 + (np.arange(nu) + 0.5) * s
    vv = v0 + (np.arange(nv) + 0.5) * s
    U, V = np.meshgrid(uu, vv)              # rows = v, cols = u
    X, Y = U + V, V - U
    ix = np.floor(X / rs).astype(int)
    iy = rh - 1 - np.floor(Y / rs).astype(int)
    ok = (ix >= 0) & (ix < rw) & (iy >= 0) & (iy < rh)
    inside = np.zeros_like(ok)
    inside[ok] = mark_bits[iy[ok], ix[ok]]

    rmask = db.Region()
    for j in range(nv):
        row = inside[j]
        i = 0
        while i < nu:
            if row[i]:
                i0 = i
                while i < nu and row[i]:
                    i += 1
                rmask.insert(db.Box(u0 + i0 * s, v0 + j * s, u0 + i * s, v0 + (j + 1) * s))
            else:
                i += 1
    rmask.merge()

    lines, n = horizontal_grating(u0, u0 + nu * s, v0, v0 + nv * s,
                                  line_w / r2, p_near / r2, p_far / r2)
    art = clean(lines & rmask, min_feature / r2, min_area / 2)

    # Map back to the real frame: (u,v) -> (u+v, v-u).  Integer, exact, on grid.
    out = db.Region()
    for poly in art.each_merged():
        out.insert(db.Polygon([db.Point(pt.x + pt.y, pt.y - pt.x) for pt in poly.each_point_hull()]))
    out.merge()
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logo", help="SVG logo")
    ap.add_argument("out")
    ap.add_argument("--cellname", default="outerfab_logo")
    ap.add_argument("--width", type=float, default=1900, help="logo (ink) width in um")
    ap.add_argument("--mask-px", type=float, default=0.5, help="mask raster pitch in um")
    ap.add_argument("--line", type=float, default=1.0, help="line width um")
    ap.add_argument("--pitch-top", type=float, default=1.46, help="wordmark pitch at the top")
    ap.add_argument("--pitch-bottom", type=float, default=2.0, help="wordmark pitch at the bottom")
    ap.add_argument("--mark-elements", default="0,1",
                    help="comma-separated indices of top-level SVG elements forming the mark "
                         "(diagonal grating); the rest form the wordmark. Empty = all horizontal")
    ap.add_argument("--mark-pitch-near", type=float, default=1.46, help="mark pitch at the square (upper-right)")
    ap.add_argument("--mark-pitch-far", type=float, default=2.0, help="mark pitch at the lower-left of the ring")
    ap.add_argument("--layer", default="81/0", help="grating layer (81/0 = Metal5)")
    ap.add_argument("--min-feature", type=float, default=0.30, help="opening size to kill slivers")
    ap.add_argument("--min-area", type=float, default=0.15, help="drop polygons below this area (um^2)")
    ap.add_argument("--boundary", nargs="*", default=["0/0", "152/5"])
    ap.add_argument("--lef", help="also write a blackbox LEF (OBS on Metal1-5) to this path")
    ap.add_argument("--lib", help="also write an empty liberty cell to this path")
    ap.add_argument("--verilog", help="also write a blackbox verilog stub to this path")
    a = ap.parse_args()

    ly = db.Layout(); ly.dbu = 0.001
    top = ly.create_cell(a.cellname)

    # --- rasterise full logo, find ink bbox, choose a raster width so ink == --width
    full = open(a.logo, "rb").read()
    w = round(a.width / a.mask_px)
    bw = rasterise(full, w)
    box = bw.getbbox()
    scale_w = round(w * bw.width / (box[2] - box[0]))
    bw = rasterise(full, scale_w)
    box = bw.getbbox()
    W = (box[2] - box[0]) * a.mask_px
    H = (box[3] - box[1]) * a.mask_px

    n_children = len(list(ET.parse(a.logo).getroot()))
    mark_idx = set(int(i) for i in a.mark_elements.split(",") if i.strip() != "")
    text_idx = set(range(n_children)) - mark_idx

    def group_bitmap(idx):
        if not idx:
            return None
        return rasterise(svg_subset(a.logo, idx), scale_w).crop(box)

    text_bw = group_bitmap(text_idx)
    mark_bw = group_bitmap(mark_idx)
    text_mask = bitmap_to_region(text_bw, a.mask_px) if text_bw else db.Region()
    mark_mask = bitmap_to_region(mark_bw, a.mask_px) if mark_bw else db.Region()

    art = db.Region()
    report = []
    if not text_mask.is_empty():
        lines, n = horizontal_grating(0, snap(W * 1000), 0, snap(H * 1000), a.line, a.pitch_top, a.pitch_bottom)
        t = clean(lines & text_mask, a.min_feature, a.min_area)
        art += t
        report.append(f"wordmark: {n} horizontal lines, pitch {a.pitch_top}->{a.pitch_bottom}, "
                      f"{t.count()} polygons, {100*t.area()/text_mask.area():.1f}% of its ink")
    if not mark_mask.is_empty():
        m, n = diagonal_grating_region(np.array(mark_bw) > 0, a.mask_px, a.line,
                                       a.mark_pitch_far, a.mark_pitch_near, a.min_feature, a.min_area)
        art += m
        report.append(f"mark: {n} -45deg lines, pitch {a.mark_pitch_near} (square) -> {a.mark_pitch_far} (ring), "
                      f"{m.count()} polygons, {100*m.area()/mark_mask.area():.1f}% of its ink")
    art.merge()

    # --- sanity: grid and angles (what geom.drc checks)
    bad_grid = sum(1 for p in art.each() for pt in p.each_point_hull() if pt.x % GRID or pt.y % GRID)
    bad_ang = 0
    for p in art.each():
        for e in p.each_edge():
            dx, dy = abs(e.dx()), abs(e.dy())
            if not (dx == 0 or dy == 0 or dx == dy):
                bad_ang += 1
    assert bad_grid == 0 and bad_ang == 0, f"off-grid vertices {bad_grid}, bad angles {bad_ang}"

    l, dt = map(int, a.layer.split("/"))
    top.shapes(ly.layer(l, dt)).insert(art)
    for b in a.boundary:
        l, dt = map(int, b.split("/"))
        top.shapes(ly.layer(l, dt)).insert(db.Box(0, 0, snap(W * 1000), snap(H * 1000)))
    ly.write(a.out)
    print(f"{a.out}: {W:.1f} x {H:.1f} um; " + "; ".join(report) +
          f"; total {art.count()} polygons, {100*art.area()*1e-6/(W*H):.1f}% of bbox")

    if a.lef:
        obs = "\n".join(f"      LAYER Metal{i} ;\n        RECT 0.0 0.0 {W:.3f} {H:.3f} ;" for i in range(1, 6))
        open(a.lef, "w").write(f"""VERSION 5.7 ;
  NOWIREEXTENSIONATPIN ON ;
  DIVIDERCHAR "/" ;
  BUSBITCHARS "[]" ;
MACRO {a.cellname}
  CLASS BLOCK ;
  FOREIGN {a.cellname} ;
  ORIGIN 0.000 0.000 ;
  SIZE {W:.3f} BY {H:.3f} ;
  OBS
{obs}
  END
END {a.cellname}
END LIBRARY
""")
    if a.lib:
        open(a.lib, "w").write(f"""library ({a.cellname}) {{
  input_threshold_pct_fall: 50.0;
  input_threshold_pct_rise: 50.0;
  output_threshold_pct_fall: 50.0;
  output_threshold_pct_rise: 50.0;
  slew_lower_threshold_pct_fall: 20.0;
  slew_lower_threshold_pct_rise: 20.0;
  slew_upper_threshold_pct_fall: 80.0;
  slew_upper_threshold_pct_rise: 80.0;

  cell ({a.cellname}) {{
  }}
}}
""")
    if a.verilog:
        open(a.verilog, "w").write(f"(* blackbox *)\nmodule {a.cellname};\nendmodule\n")


if __name__ == "__main__":
    main()
