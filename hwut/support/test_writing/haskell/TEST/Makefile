# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The Haskell test applications: 'test-x.exe' from 'test-x.hs' and the support
# modules it imports ('../Hwut/'), compiled by 'ghc --make'. NOTHING IS SHARED
# BETWEEN TWO TARGETS: each compiles its own copy of the support modules into
# 'build-<stem>/' ('-outputdir'), so hwut may build several tests of this
# directory at once (services E-210: the build runs here, where this Makefile
# stands). GHC and its boot packages alone -- no cabal, no Hackage.
#
# '-dynamic': the executable links GHC's shared boot libraries, some 20 KB
# instead of some 14 MB -- below the default file cap of a run.
# '-package-env -': no environment file of the user's changes the packages.
#
# 'test-hwut_vterm' binds the C port ('../../c/hwut_vterm.c'): 'hsc2hs' reads
# its header's structure offsets into 'build-<stem>/generated/Hwut/Vterm.hs',
# and the C source is compiled into 'build-<stem>/' by the C compiler (given
# to ghc, its object would land beside the source).
#______________________________________________________________________________
GHC      ?= ghc
HSC2HS   ?= hsc2hs
CC       ?= cc
GHCFLAGS ?= -O0 -v0
GHC_ALL   = $(GHCFLAGS) -dynamic -package-env - -i$(SUPPORT)
SUPPORT   = ..
C_PORT    = ../../c
LIBRARY   = $(wildcard $(SUPPORT)/Hwut/*.hs) $(wildcard $(SUPPORT)/Hwut/*.hsc)

%.exe: %.hs $(LIBRARY)
	$(GHC) $(GHC_ALL) -outputdir build-$* -o $@ $<

test-hwut_vterm.exe: test-hwut_vterm.hs $(LIBRARY) $(C_PORT)/hwut_vterm.c $(C_PORT)/hwut_vterm.h
	mkdir -p build-test-hwut_vterm/generated/Hwut
	$(HSC2HS) -I$(C_PORT) -o build-test-hwut_vterm/generated/Hwut/Vterm.hs $(SUPPORT)/Hwut/Vterm.hsc
	$(CC) -std=c99 -O1 -fPIC -c -o build-test-hwut_vterm/hwut_vterm_c.o $(C_PORT)/hwut_vterm.c
	$(GHC) $(GHC_ALL) -ibuild-test-hwut_vterm/generated -outputdir build-test-hwut_vterm -o $@ $< \
	       build-test-hwut_vterm/hwut_vterm_c.o -ldl -lutil

all: test-deterministic-random.exe test-deterministic-timeline.exe test-space-iterator.exe \
     test-hwut_fsm.exe test-hwut_hocon.exe test-hwut_vterm.exe

clean:
	rm -rf *.exe build-*

.PHONY: all clean
