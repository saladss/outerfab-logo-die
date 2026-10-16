#!/usr/bin/env python3
"""Portrait photo -> 1-bit halftone -> Metal5 GDS macro.

Pipeline: remove background (rembg), keep only the head with a soft ellipse,
convert to greyscale (metal = bright), Floyd-Steinberg dither, then draw each
row of set pixels as horizontal boxes `pixel` um pitch and `pixel - gap` um tall.
Rows never touch (gap >= M5 min space) so there are no corner-to-corner
contacts for DRC to complain about.
"""
import argparse
import numpy as np
import klayout.db as db
from PIL import Image, ImageDraw, ImageOps, ImageFilter

GRID = 5


def snap(nm):
    return int(round(nm / GRID)) * GRID


def cutout(src, ellipse, blur=4, flip=False, erase=()):
    from rembg import remove, new_session
    im = remove(Image.open(src).convert("RGBA"), session=new_session("u2net"))
    if flip:
        im = ImageOps.mirror(im)
    if ellipse:
        cx, cy, ax, ay = ellipse
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).ellipse([cx - ax, cy - ay, cx + ax, cy + ay], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(blur))
        a = np.array(im.split()[3]).astype(float) * np.array(m) / 255
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
    if erase:
        d = ImageDraw.Draw(im)
        for x0, y0, x1, y1 in erase:
            d.rectangle([x0, y0, x1, y1], fill=(0, 0, 0, 0))
    return im.crop(im.getbbox())


def halftone(im, height_px, invert=False, gamma=1.0, contrast=1.0):
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    bg.paste(im, (0, 0), im)
    g = ImageOps.autocontrast(bg.convert("L"), cutoff=1)
    if gamma != 1.0 or contrast != 1.0:
        lut = [min(255, max(0, round(255 * (((v / 255) ** gamma - 0.5) * contrast + 0.5)))) for v in range(256)]
        g = g.point(lut)
    if invert:
        g = ImageOps.invert(g)
    g = g.resize((round(g.width * height_px / g.height), height_px), Image.LANCZOS)
    return g.convert("1", dither=Image.FLOYDSTEINBERG)


def to_gds(bits, out, cellname, pixel, gap, layer, boundary):
    ly = db.Layout(); ly.dbu = 0.001
    top = ly.create_cell(cellname)
    a = np.array(bits) > 0
    H, W = a.shape
    p = snap(pixel * 1000); g = snap(gap * 1000)
    reg = db.Region()
    for y in range(H):
        row = a[y]; x = 0
        while x < W:
            if row[x]:
                x0 = x
                while x < W and row[x]:
                    x += 1
                yb = (H - y - 1) * p
                reg.insert(db.Box(x0 * p, yb + g, x * p - g, yb + p))
            else:
                x += 1
    l, dt = map(int, layer.split("/"))
    top.shapes(ly.layer(l, dt)).insert(reg)
    Wum, Hum = W * pixel, H * pixel
    for b in boundary:
        l, dt = map(int, b.split("/"))
        top.shapes(ly.layer(l, dt)).insert(db.Box(0, 0, snap(Wum * 1000), snap(Hum * 1000)))
    ly.write(out)
    return Wum, Hum, reg.count(), reg.area() * 1e-6 / (Wum * Hum)


def write_views(cellname, W, H, lef, lib, verilog):
    if lef:
        obs = "\n".join(f"      LAYER Metal{i} ;\n        RECT 0.0 0.0 {W:.3f} {H:.3f} ;" for i in range(1, 6))
        open(lef, "w").write(f"""VERSION 5.7 ;
  NOWIREEXTENSIONATPIN ON ;
  DIVIDERCHAR "/" ;
  BUSBITCHARS "[]" ;
MACRO {cellname}
  CLASS BLOCK ;
  FOREIGN {cellname} ;
  ORIGIN 0.000 0.000 ;
  SIZE {W:.3f} BY {H:.3f} ;
  OBS
{obs}
  END
END {cellname}
END LIBRARY
""")
    if lib:
        open(lib, "w").write(f"""library ({cellname}) {{
  input_threshold_pct_fall: 50.0;
  input_threshold_pct_rise: 50.0;
  output_threshold_pct_fall: 50.0;
  output_threshold_pct_rise: 50.0;
  slew_lower_threshold_pct_fall: 20.0;
  slew_lower_threshold_pct_rise: 20.0;
  slew_upper_threshold_pct_fall: 80.0;
  slew_upper_threshold_pct_rise: 80.0;

  cell ({cellname}) {{
  }}
}}
""")
    if verilog:
        open(verilog, "w").write(f"(* blackbox *)\nmodule {cellname};\nendmodule\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("out")
    ap.add_argument("--cellname", required=True)
    ap.add_argument("--ellipse", type=float, nargs=4, metavar=("CX", "CY", "AX", "AY"),
                    help="head ellipse in source-photo pixels (after background removal); omit to keep all")
    ap.add_argument("--height", type=float, default=540, help="portrait height in um")
    ap.add_argument("--pixel", type=float, default=2.0, help="halftone pixel pitch in um")
    ap.add_argument("--gap", type=float, default=0.3, help="gap between rows in um (>= M5 min space)")
    ap.add_argument("--invert", action="store_true", help="metal = dark instead of metal = bright")
    ap.add_argument("--gamma", type=float, default=1.0, help="<1 brightens mid-tones")
    ap.add_argument("--contrast", type=float, default=1.0, help=">1 stretches around mid-grey")
    ap.add_argument("--flip", action="store_true", help="mirror horizontally (ellipse is given in flipped coords)")
    ap.add_argument("--erase", type=float, nargs=4, action="append", metavar=("X0", "Y0", "X1", "Y1"), default=[],
                    help="rectangle(s) to blank out, in (flipped) photo pixels; repeatable")
    ap.add_argument("--layer", default="81/0")
    ap.add_argument("--boundary", nargs="*", default=["0/0", "152/5"])
    ap.add_argument("--bitmap", help="also save the dithered bitmap PNG here")
    ap.add_argument("--lef"); ap.add_argument("--lib"); ap.add_argument("--verilog")
    a = ap.parse_args()

    head = cutout(a.photo, a.ellipse, flip=a.flip, erase=a.erase)
    bits = halftone(head, round(a.height / a.pixel), a.invert, a.gamma, a.contrast)
    if a.bitmap:
        bits.save(a.bitmap)
    W, H, n, cov = to_gds(bits, a.out, a.cellname, a.pixel, a.gap, a.layer, a.boundary)
    write_views(a.cellname, W, H, a.lef, a.lib, a.verilog)
    print(f"{a.out}: {W:.1f} x {H:.1f} um, {bits.width}x{bits.height} px, {n} boxes, M5 coverage {100*cov:.1f}%")


if __name__ == "__main__":
    main()
