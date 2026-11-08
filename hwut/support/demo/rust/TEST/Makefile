# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S PROGRAMS: 'x.exe' from 'x.rs'. hwut runs this Makefile
# here, where it stands (services E-210), once per test that says
# 'build { framework = "make", target = "%.exe" }'; 'on_entry' runs
# 'make helpers' -- the programs that are no tests, and 'shop.exe' which
# 'delivery.json' runs -- before any test is built.
#
# NOTHING IS SHARED BETWEEN TWO TARGETS, so hwut may build several at once:
# a test that uses the support crate 'hwut' compiles its own copy of it into
# 'build-<stem>/libhwut.rlib'. rustc alone, offline -- no cargo, no crate
# from outside. '+': rustc joins make's jobserver.
#
# WHERE THE SUPPORT STANDS is said on ONE line, the one marked below: the
# variable HWUT_SUPPORT_RUST where it is set (Rust has no search path of its
# own for a crate), else the port beside the demonstration in hwut's tree.
#______________________________________________________________________________
RUSTC      ?= rustc
RUSTFLAGS  ?= --edition 2021 -O
SUPPORT_AT  = $(or $(HWUT_SUPPORT_RUST),../../../test_writing/rust)# HWUT-SUPPORT-PATH
SUPPORT     = $(strip $(SUPPORT_AT))
LIBRARY_RS  = $(wildcard $(SUPPORT)/src/*.rs)

HELPERS     = fixture.exe viewer.exe producer.exe shop.exe

#  The tests that link the support crate.
garage.exe screen.exe: %.exe: %.rs $(LIBRARY_RS)
	mkdir -p build-$*
	+$(RUSTC) $(RUSTFLAGS) --crate-type rlib --crate-name hwut -o build-$*/libhwut.rlib $(SUPPORT)/src/lib.rs
	+$(RUSTC) $(RUSTFLAGS) --crate-type bin --extern hwut=build-$*/libhwut.rlib -L build-$* -o $@ $<

#  The programs that stand alone; their modules are sources, not outputs.
demo.exe chamber.exe build.exe producer.exe: %.exe: %.rs clock_random.rs
	+$(RUSTC) $(RUSTFLAGS) --crate-type bin -o $@ $<

shop.exe fixture.exe: %.exe: %.rs shop_db.rs
	+$(RUSTC) $(RUSTFLAGS) --crate-type bin -o $@ $<

door.exe viewer.exe: %.exe: %.rs
	+$(RUSTC) $(RUSTFLAGS) --crate-type bin -o $@ $<

helpers: $(HELPERS)

all: demo.exe chamber.exe build.exe door.exe garage.exe screen.exe $(HELPERS)

clean:
	rm -rf *.exe build-*

.PHONY: helpers all clean
