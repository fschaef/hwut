# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The Rust test applications: 'test-x.exe' from 'test-x.rs' and the support
# library crate 'hwut' ('../src/lib.rs', an rlib). NOTHING IS SHARED BETWEEN
# TWO TARGETS: each builds its own copy of the rlib in 'build-<stem>/', so
# hwut may build several tests of this directory at once (services E-210:
# the build runs here, where this Makefile stands). rustc alone, offline --
# no cargo, no crate from outside. '+': rustc joins make's jobserver.
#______________________________________________________________________________
RUSTC      ?= rustc
RUSTFLAGS  ?= --edition 2021 -O
SUPPORT     = ..
LIBRARY_RS  = $(wildcard $(SUPPORT)/src/*.rs)

%.exe: %.rs $(LIBRARY_RS)
	mkdir -p build-$*
	+$(RUSTC) $(RUSTFLAGS) --crate-type rlib --crate-name hwut -o build-$*/libhwut.rlib $(SUPPORT)/src/lib.rs
	+$(RUSTC) $(RUSTFLAGS) --crate-type bin --extern hwut=build-$*/libhwut.rlib -L build-$* -o $@ $<

all: test-deterministic-random.exe test-deterministic-timeline.exe test-space-iterator.exe \
     test-hwut_fsm.exe test-hwut_hocon.exe test-hwut_vterm.exe

clean:
	rm -rf *.exe build-*

.PHONY: all clean
