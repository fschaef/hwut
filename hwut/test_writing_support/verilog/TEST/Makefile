# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The SystemVerilog test applications, each built WHOLE by Verilator from its
# source, the SystemVerilog packages it imports ('..') and the C it reaches
# through DPI-C: the DPI faces ('../*_dpi.c') and the C modules they wrap
# ('../../c/*.c'). The C is compiled as C, by $(CC), into a directory of the
# target's own ('<target>.obj', removed after the link), and Verilator
# builds its C++ there too: no file is shared between two targets, so hwut
# may build several tests of this directory at once (services E-210: the
# build runs here, where this Makefile stands).
#
# '<target>.exe' is the simulation itself ('verilator --binary'): hwut calls
# it with a choice, '--hwut-info' or '--interactive' as any test application.
#______________________________________________________________________________
VERILATOR ?= verilator
CC        ?= cc
CFLAGS    ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
VFLAGS    ?= --binary -j 2 -Wno-fatal -Wno-lint -Wno-style -Wno-IMPLICITSTATIC
SUPPORT    = ..
C_SUPPORT  = ../../c
VLTSTD     = $(shell $(VERILATOR) --getenv VERILATOR_ROOT)/include/vltstd
HEADER     = $(wildcard $(C_SUPPORT)/*.h)
LIBRARY    = $(SUPPORT)/hwut_pytext.sv $(SUPPORT)/hwut_runner.sv \
             $(SUPPORT)/hwut_pytext_dpi.c $(SUPPORT)/hwut_runner_dpi.c $(C_SUPPORT)/hwut_pytext.c

# $(call build,<libraries>): the C sources among the prerequisites compiled
# as C into '$@.obj'; Verilator there, the packages in the order given, the
# test's own source last, its module the top; the simulation copied out.
define build
	rm -rf $@.obj && mkdir $@.obj
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) -I$(C_SUPPORT) -I$(VLTSTD) -c $$c -o $@.obj/$$(basename $$c .c).o || exit 1; \
	done
	$(VERILATOR) $(VFLAGS) --Mdir $@.obj -o simulation --top-module $(subst -,_,$(basename $<)) \
	    $(filter-out $<,$(filter %.sv,$^)) $< $(abspath $@.obj)/*.o $(1) > $@.obj/build.log 2>&1 \
	    || { cat $@.obj/build.log; rm -rf $@.obj; exit 1; }
	cp $@.obj/simulation $@
	rm -rf $@.obj
endef

test-deterministic-random.exe: test-deterministic-random.sv $(LIBRARY) $(SUPPORT)/deterministic_random.sv
	$(call build,)

test-deterministic-timeline.exe: test-deterministic-timeline.sv $(LIBRARY) $(SUPPORT)/deterministic_timeline.sv
	$(call build,)

test-space-iterator.exe: test-space-iterator.sv $(LIBRARY) $(SUPPORT)/space_iterator.sv
	$(call build,)

test-hwut_fsm.exe: test-hwut_fsm.sv $(LIBRARY) $(SUPPORT)/hwut_fsm.sv $(SUPPORT)/hwut_fsm_dpi.c \
	           $(C_SUPPORT)/hwut_fsm.c $(HEADER)
	$(call build,)

test-hwut_hocon.exe: test-hwut_hocon.sv $(LIBRARY) $(SUPPORT)/deterministic_random.sv $(SUPPORT)/hwut_hocon.sv \
	             $(SUPPORT)/hwut_hocon_dpi.c $(C_SUPPORT)/hwut_hocon.c $(HEADER)
	$(call build,)

test-hwut_vterm.exe: test-hwut_vterm.sv $(LIBRARY) $(SUPPORT)/hwut_vterm.sv $(SUPPORT)/hwut_vterm_dpi.c \
	             $(C_SUPPORT)/hwut_vterm.c $(HEADER)
	$(call build,-LDFLAGS "-ldl -lutil")

clean:
	rm -rf *.exe *.exe.obj

.PHONY: clean
