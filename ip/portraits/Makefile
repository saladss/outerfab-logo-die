# Founder portraits as Metal5 halftones, placed above (stuart) and below (giovanni) the VGA macro.
# --ellipse is the head region in source-photo pixels (cx cy ax ay); tune per photo.

all: giovanni stuart
.PHONY: all giovanni stuart

giovanni:
	python3 script/make_portrait.py photo/giovanni.png gds/portrait_giovanni.gds --cellname portrait_giovanni --flip \
		--ellipse 238 296 240 262 --gamma 1.15 --white 0.8 --height 540 --pixel 1.5 --bitmap bitmap/giovanni.png \
		--lef lef/portrait_giovanni.lef --lib lib/portrait_giovanni.lib --verilog vh/portrait_giovanni.v

stuart:
	python3 script/make_portrait.py photo/stuart.png gds/portrait_stuart.gds --cellname portrait_stuart --flip \
		--ellipse 350 505 365 385 --erase 130 0 275 150 --erase 320 0 410 118 --gamma 1.0 --contrast 1.3 --white 0.7 \
		--height 540 --pixel 1.5 --bitmap bitmap/stuart.png \
		--lef lef/portrait_stuart.lef --lib lib/portrait_stuart.lib --verilog vh/portrait_stuart.v
