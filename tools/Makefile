# Build for the TestU01 Alphabit probe and batch driver.
#
# TestU01 is built by tools/build_testu01.sh into a space-free directory
# under $HOME (TestU01's libtool build cannot run in a path with a space, and
# this repo lives under ".../Master Thesis/..."). Run that script first, then:
#
#   make -C tools
#
#   alphabit_probe   -- Phase 0 single-stream smoke probe
#   alphabit_driver  -- batch driver used by the Exp 3 / Exp 4 pipeline
#
# TU01 must match TESTU01_HOME in build_testu01.sh. Override if you changed it.
# Paths are quoted defensively in case TU01 is pointed at a path with a space.

TU01 ?= $(HOME)/.cache/cryptoentropy-rng/testu01

CC     ?= cc
CFLAGS ?= -O2 -Wall
INCS   := -I"$(TU01)/include"
LIBS   := -L"$(TU01)/lib" -ltestu01 -lprobdist -lmylib -lm

.PHONY: all clean
all: alphabit_probe alphabit_driver

alphabit_probe: alphabit_probe.c
	$(CC) $(CFLAGS) $(INCS) -o $@ $< $(LIBS)

alphabit_driver: alphabit_driver.c
	$(CC) $(CFLAGS) $(INCS) -o $@ $< $(LIBS)

clean:
	rm -f alphabit_probe alphabit_driver
