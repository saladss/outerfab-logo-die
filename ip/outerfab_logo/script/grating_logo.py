#!/usr/bin/env python3
"""Render a logo as a chirped diffraction grating in GDS.

The logo silhouette (from an SVG or PNG) is filled with horizontal metal lines of
constant width whose pitch sweeps linearly from --pitch-top to --pitch-bottom, so
the diffracted colour changes from top to bottom under directional light.
Inspired by Tholin's palette_1 test structures (AvalonSemiconductors/ws-submission-2026).
"""
import argparse
import klayout.db as db
from PIL import Image
import cairosvg, io


def rasterise(path, w):
    if path.lower().endswith(".svg"):
        png = cairosvg.svg2png(url=path, output_width=w, background_color="white")
        img = Image.open(io.BytesIO(png))
    else:
        img = Image.open(path)
        img = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    bg = Image.new("RGBA", img.size, "WHITE")
    bg.paste(img.convert("RGBA"), (0, 0), img.convert("RGBA"))
    return bg.convert("L").point(lambda v: 0 if v > 128 else 255)  # dark -> 255


def load_mask(path, width_um, mask_px, crop=True):
    """Return a merged Region of the dark logo pixels, mask_px um per pixel.

    With crop=True the artwork's own bounding box (ignoring blank margins in the
    source file) is scaled to width_um, so the ink spans the full width."""
    w = round(width_um / mask_px)
    bw = rasterise(path, w)
    if crop:
        box = bw.getbbox()  # bbox of non-zero (dark) pixels
        if box:
            ink_w = box[2] - box[0]
            # re-rasterise so the ink itself is w pixels wide, then crop
            bw = rasterise(path, round(w * bw.width / ink_w))
            bw = bw.crop(bw.getbbox())
    reg = db.Region()
    H = bw.height
    px = bw.load()
    for y in range(H):
        x = 0
        while x < bw.width:
            if px[x, y]:
                x0 = x
                while x < bw.width and px[x, y]:
                    x += 1
                reg.insert(db.Box(round(x0 * mask_px * 1000), round((H - y - 1) * mask_px * 1000),
                                  round(x * mask_px * 1000), round((H - y) * mask_px * 1000)))
            else:
                x += 1
    reg.merge()
    return reg, bw.width * mask_px, H * mask_px


def grating(width_um, height_um, line_w, p_top, p_bot):
    """Horizontal lines; pitch sweeps linearly from p_top (at top) to p_bot (at bottom)."""
    reg = db.Region()
    y = height_um  # start at top edge, walk downward
    pitches = []
    while y - line_w >= 0:
        frac = 1 - y / height_um        # 0 at top, 1 at bottom
        p = p_top + (p_bot - p_top) * frac
        pitches.append(p)
        y1 = y
        y0 = y - line_w
        reg.insert(db.Box(0, round(y0 * 1000), round(width_um * 1000), round(y1 * 1000)))
        y -= p
    return reg, len(pitches)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logo")
    ap.add_argument("out")
    ap.add_argument("--cellname", default="outerfab_logo")
    ap.add_argument("--width", type=float, default=2300, help="logo width in um")
    ap.add_argument("--mask-px", type=float, default=0.5, help="mask raster pitch in um")
    ap.add_argument("--line", type=float, default=1.0, help="line width um")
    ap.add_argument("--pitch-top", type=float, default=1.46)
    ap.add_argument("--pitch-bottom", type=float, default=2.0)
    ap.add_argument("--layer", default="81/0", help="grating layer (81/0 = Metal5)")
    ap.add_argument("--min-feature", type=float, default=0.30, help="opening size to kill slivers")
    ap.add_argument("--boundary", nargs="*", default=["0/0", "152/5"])
    ap.add_argument("--no-crop", action="store_true", help="keep the source file's blank margins")
    ap.add_argument("--lef", help="also write a blackbox LEF (OBS on Metal1-5) to this path")
    ap.add_argument("--lib", help="also write an empty liberty cell to this path")
    ap.add_argument("--verilog", help="also write a blackbox verilog stub to this path")
    a = ap.parse_args()

    ly = db.Layout(); ly.dbu = 0.001
    top = ly.create_cell(a.cellname)

    mask, W, H = load_mask(a.logo, a.width, a.mask_px, crop=not a.no_crop)
    lines, n = grating(W, H, a.line, a.pitch_top, a.pitch_bottom)
    art = (lines & mask).merged()
    d = round(a.min_feature / 2 * 1000)
    art = art.sized(-d).sized(d).merged()           # opening: removes anything thinner than min_feature
    art = art.with_area(round(0.15 * 1e6), None, False)  # drop tiny islands (M5 min area 0.1444 um^2)

    l, dt = map(int, a.layer.split("/"))
    top.shapes(ly.layer(l, dt)).insert(art)
    for b in a.boundary:
        l, dt = map(int, b.split("/"))
        top.shapes(ly.layer(l, dt)).insert(db.Box(0, 0, round(W * 1000), round(H * 1000)))
    ly.write(a.out)

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

    bbox = W * H
    print(f"{a.out}: {W:.1f} x {H:.1f} um, {n} lines, pitch {a.pitch_top}->{a.pitch_bottom} um, "
          f"{art.count()} polygons, layer coverage {100*art.area()*1e-6/bbox:.1f}% of bbox, "
          f"{100*art.area()/mask.area():.1f}% of logo area")


if __name__ == "__main__":
    main()
