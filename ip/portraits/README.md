# Founder portraits

Halftone portraits of the outerfab founders on Metal5, placed in the right-hand column of the
die: Stuart above the VGA macro, Giovanni below it.

`script/make_portrait.py` removes the photo background (rembg / u2net), keeps the head with a
soft ellipse (`--ellipse cx cy ax ay` in photo pixels, `--erase` rectangles for stray
background), applies an optional tone curve, Floyd-Steinberg dithers to 1-bit at `--pixel` um
per pixel, and writes each row of set pixels as boxes with a 0.3 um row gap (so no two shapes
touch corner-to-corner). Metal = bright areas of the photo. `make all` regenerates both.

Photos are the founders' own; not licensed for reuse outside this project.
