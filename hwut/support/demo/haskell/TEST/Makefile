# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S PROGRAMS: 'x.exe' from 'x.hs', compiled by 'ghc --make'
# with the support modules it imports. hwut builds a test where this
# Makefile stands (services E-210), several tests at once: NOTHING IS SHARED
# BETWEEN TWO TARGETS -- each compiles its own copy of every module it
# imports into 'build-<stem>/' ('-outputdir').
#
#     demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe
#                       the tests -- hwut builds each by its header's 'build'
#     viewer.exe        the program 'screen.exe' runs: built with it
#     fixture.exe producer.exe
#                       helpers -- 'on_entry' in 'hwut.conf' builds them,
#                       and 'shop.exe', which 'delivery.json' is executed by
#
# WHERE THE HASKELL TEST SUPPORT STANDS is said on the ONE line below: GHC
# has no variable of the environment for a source directory to import from,
# so the variable HWUT_SUPPORT_HASKELL says it, where the environment sets it
# ('?=': the environment wins); the port beside this demonstration else.
# 'screen.exe' binds the C port of hwut_vterm, as the Haskell port's own
# tests do: it stands beside the Haskell port, in '$(SUPPORT)/../c'.
#
# '-dynamic' links GHC's shared boot libraries (an executable of some 300 KB,
# not 14 MB: below a run's default file cap); '-package-env -': no
# environment file of the user's changes the packages; '-threaded' where a
# program runs threads of its own.
#______________________________________________________________________________
HWUT_SUPPORT_HASKELL ?= ../../../test_writing/haskell    # HWUT-SUPPORT-PATH
GHC      ?= ghc
HSC2HS   ?= hsc2hs
CC       ?= cc
GHCFLAGS ?= -O0 -v0
SUPPORT   = $(strip $(HWUT_SUPPORT_HASKELL))
C_PORT    = $(SUPPORT)/../c
LIBRARY   = $(wildcard $(SUPPORT)/Hwut/*.hs)
GHC_ALL   = $(GHCFLAGS) -dynamic -package-env - -i$(SUPPORT) -outputdir build-$* -o $@

%.exe: %.hs
	$(GHC) $(GHC_ALL) $<

#  Threads of their own: the threaded runtime.
demo.exe build.exe producer.exe: %.exe: %.hs ClockRandom.hs
	$(GHC) $(GHC_ALL) -threaded $<

chamber.exe: %.exe: %.hs ClockRandom.hs $(LIBRARY)
	$(GHC) $(GHC_ALL) $<

garage.exe: %.exe: %.hs $(LIBRARY)
	$(GHC) $(GHC_ALL) $<

#  SQLite, by the C library ('Sqlite.hs' binds it).
shop.exe fixture.exe: %.exe: %.hs Sqlite.hs
	$(GHC) $(GHC_ALL) -threaded $< -lsqlite3

#  'Hwut.Vterm' is a '.hsc' over the C port: 'hsc2hs' reads the C header's
#  structure offsets into 'build-screen/generated/', the C source is compiled
#  into 'build-screen/' (given to ghc, its object would land beside the
#  source).
screen.exe: %.exe: %.hs viewer.exe $(SUPPORT)/Hwut/Vterm.hsc $(C_PORT)/hwut_vterm.c $(C_PORT)/hwut_vterm.h
	mkdir -p build-screen/generated/Hwut
	$(HSC2HS) -I$(C_PORT) -o build-screen/generated/Hwut/Vterm.hs $(SUPPORT)/Hwut/Vterm.hsc
	$(CC) -std=c99 -O1 -fPIC -c -o build-screen/hwut_vterm_c.o $(C_PORT)/hwut_vterm.c
	$(GHC) $(GHC_ALL) -ibuild-screen/generated $< build-screen/hwut_vterm_c.o -ldl -lutil

all: demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe \
     fixture.exe producer.exe

clean:
	rm -rf *.exe build-*

.PHONY: all clean
