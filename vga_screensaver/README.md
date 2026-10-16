# VGA screensaver macro

DVD-style bouncing **outerfab** mark over VGA (640x480, Tiny VGA Pmod), hardened as a
500 x 500 um macro and placed in the right-hand column of the die.

Based on [TinyTapeout/tt-waferspace-vga-screensaver](https://github.com/TinyTapeout/tt-waferspace-vga-screensaver)
by Uri Shaked (Apache-2.0, see `LICENSE.screensaver`); the logo ROM has been replaced with the
outerfab mark (`art/logo.png`, 128x128). To change the logo, replace `art/logo.png` and run
`python3 make_bitmap.py` from `art/`.

Harden with `make vga` from the repository root (writes `runs/latest/final/`), then run the
top-level flow.

Controls (see `src/chip_core.sv` for the pad map): `tile` repeats the logo across the screen,
`solid_color` disables the animated gradient, and a Gamepad Pmod can pause/steer the logo.
