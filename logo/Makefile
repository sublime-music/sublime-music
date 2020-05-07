DIMENS=16 22 24 32 36 48 64 72 96 128 192 512 1024
PNGFILES=$(patsubst %, rendered/%.png, $(DIMENS))

all: $(PNGFILES)

rendereddir:
	mkdir -p rendered

rendered/%.png: icon.svg | rendereddir
	inkscape --export-filename=$@ -w $(*F) $<

clean:
	rm -rf rendered
