# outerfab logo as a chirped Metal5 diffraction grating.
# 1 um lines, pitch sweeping 1.46 -> 2.0 um top to bottom (range seen to
# produce colour on GF180 in AvalonSemiconductors/ws-submission-2026 palette_1).

PDK_ROOT ?= ../../gf180mcu_pdk
PDK ?= gf180mcuD
CELL = outerfab_logo
WIDTH ?= 1900
PITCH_TOP ?= 1.46
PITCH_BOTTOM ?= 2.0

all: logo
.PHONY: all

logo:
	python3 script/grating_logo.py image/logo-stacked-black.svg gds/$(CELL).gds \
		--cellname $(CELL) --width $(WIDTH) --pitch-top $(PITCH_TOP) --pitch-bottom $(PITCH_BOTTOM) \
		--layer 81/0 --boundary 0/0 152/5 \
		--lef lef/$(CELL).lef --lib lib/$(CELL).lib --verilog vh/$(CELL).v
.PHONY: logo

drc:
	PDK_ROOT=${PDK_ROOT} PDK=${PDK} klayout -b -zz -r ${PDK_ROOT}/${PDK}/libs.tech/klayout/tech/drc/gf180mcu.drc -rd input=gds/$(CELL).gds -rd report=report.lyrdb -rd feol=false -rd beol=true
.PHONY: drc
