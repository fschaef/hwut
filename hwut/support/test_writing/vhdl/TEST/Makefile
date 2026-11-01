# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The VHDL test applications. 'test-x.exe' is a LAUNCHER (GHDL's mcode backend
# writes no executable): it runs the design analysed into 'test-x.work', a
# directory of the target's own that also holds 'libhwut_vhdl.so' -- the
# VHPIDIRECT glue and the C modules it wraps, compiled for this target alone.
# No file is shared between two targets, so hwut may build several tests of
# this directory at once (services E-210: the build runs here, where this
# Makefile stands).
#______________________________________________________________________________
GHDL      ?= ghdl
GHDLFLAGS ?= --std=08
CC        ?= cc
CFLAGS    ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT   = ..
C_SUPPORT = ../../c
# IN THE ORDER OF ANALYSIS: a package after the packages it uses.
PACKAGE   = $(SUPPORT)/hwut_vhpi.vhd $(SUPPORT)/hwut_pytext.vhd $(SUPPORT)/hwut_runner.vhd \
            $(SUPPORT)/deterministic_random.vhd $(SUPPORT)/deterministic_timeline.vhd \
            $(SUPPORT)/space_iterator.vhd $(SUPPORT)/hwut_fsm.vhd $(SUPPORT)/hwut_hocon.vhd \
            $(SUPPORT)/hwut_vterm.vhd
GLUE      = $(SUPPORT)/hwut_vhpi.c $(C_SUPPORT)/hwut_pytext.c $(C_SUPPORT)/hwut_fsm.c \
            $(C_SUPPORT)/hwut_hocon.c $(C_SUPPORT)/hwut_vterm.c
HEADER    = $(wildcard $(C_SUPPORT)/*.h)

# test-x.exe: test-x.vhd, entity 'test_x'.
%.exe: %.vhd $(PACKAGE) $(GLUE) $(HEADER) $(SUPPORT)/hwut_launch.sh
	rm -rf $*.work && mkdir $*.work
	$(CC) $(CFLAGS) -fPIC -shared -I$(C_SUPPORT) -o $*.work/libhwut_vhdl.so $(GLUE) -lm -ldl -lutil
	$(GHDL) -a $(GHDLFLAGS) --workdir=$*.work $(PACKAGE) $<
	printf '#! /bin/sh\nexec sh "$$(dirname "$$0")/%s" "$$(dirname "$$0")/%s" %s "$$@"\n' \
	       "$(SUPPORT)/hwut_launch.sh" "$*.work" "$(subst -,_,$*)" > $@.tmp
	chmod +x $@.tmp && mv $@.tmp $@

all: test-deterministic-random.exe test-deterministic-timeline.exe test-space-iterator.exe \
     test-hwut_fsm.exe test-hwut_hocon.exe test-hwut_vterm.exe

clean:
	rm -rf *.exe *.exe.tmp *.work

.PHONY: all clean
