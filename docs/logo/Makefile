DIMENS=16 22 24 32 36 48 64 72 96 128 192 512 1024
PNGFILES=$(patsubst %,build/%.png,$(DIMENS))

all: $(PNGFILES)

builddir:
	mkdir -p build

build/%.png: logo.svg | builddir
	inkscape -z -e $@ -w $(*F) -h $(*F) $<
