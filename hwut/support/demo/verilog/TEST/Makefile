# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S SIMULATIONS, each built WHOLE by Verilator from its
# source, the SystemVerilog packages of the test support it imports and the
# C it reaches through DPI-C. hwut builds a test where this Makefile stands
# (services E-210), several at once: every target has a directory of its own,
# '<target>.obj' (the C objects, Verilator's C++, the link), removed after --
# no file is shared between two targets.
#
#     demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe
#                       the tests -- hwut builds each by its header's 'build'
#     viewer.exe        the program 'screen.exe' runs: built with it
#     fixture.exe producer.exe shop.exe
#                       built by 'on_entry' in 'hwut.conf': the fixture and
#                       the producer are no tests, and 'delivery.json' is
#                       executed by 'shop.exe' before 'shop.sv' may be built
#
# WHERE THE SYSTEMVERILOG TEST SUPPORT STANDS is said on the ONE line below:
# the variable HWUT_SUPPORT_VERILOG where the environment sets it (it takes
# precedence: '?='), the clone's port else. The C port it reaches through
# DPI-C stands beside it, '../c' from there, as in the clone.
#______________________________________________________________________________
HWUT_SUPPORT_VERILOG ?= ../../../test_writing/verilog    # HWUT-SUPPORT-PATH
VERILATOR ?= verilator
CC        ?= cc
CFLAGS    ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
VFLAGS    ?= --binary -j 2 -Wno-fatal -Wno-lint -Wno-style -Wno-IMPLICITSTATIC
SUPPORT    = $(strip $(HWUT_SUPPORT_VERILOG))
C_SUPPORT  = $(SUPPORT)/../c
VLTSTD     = $(shell $(VERILATOR) --getenv VERILATOR_ROOT)/include/vltstd
HEADER     = $(wildcard $(C_SUPPORT)/*.h)
LIBRARY    = $(SUPPORT)/hwut_pytext.sv $(SUPPORT)/hwut_runner.sv \
             $(SUPPORT)/hwut_pytext_dpi.c $(SUPPORT)/hwut_runner_dpi.c $(C_SUPPORT)/hwut_pytext.c
RANDOM     = $(SUPPORT)/deterministic_random.sv
HOCON      = $(SUPPORT)/hwut_hocon.sv $(SUPPORT)/hwut_hocon_dpi.c $(C_SUPPORT)/hwut_hocon.c $(HEADER)

# $(call build,<link flags>): the C sources among the prerequisites compiled
# as C into '$@.obj'; Verilator there, the packages in the order given, the
# source last, its module the top; the simulation copied out.
define build
	rm -rf $@.obj && mkdir $@.obj
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) -I$(C_SUPPORT) -I$(VLTSTD) -c $$c -o $@.obj/$$(basename $$c .c).o || exit 1; \
	done
	$(VERILATOR) $(VFLAGS) --Mdir $@.obj -o simulation --top-module $(basename $<) \
	    $(filter-out $<,$(filter %.sv,$^)) $< $(if $(filter %.c,$^),$(abspath $@.obj)/*.o) $(1) \
	    > $@.obj/build.log 2>&1 || { tail -20 $@.obj/build.log >&2; rm -rf $@.obj; exit 1; }
	cp $@.obj/simulation $@
	rm -rf $@.obj
endef

demo.exe: demo.sv $(LIBRARY) $(RANDOM)
	$(call build,)

chamber.exe: chamber.sv $(LIBRARY) $(RANDOM)
	$(call build,)

door.exe: door.sv $(LIBRARY)
	$(call build,)

build.exe: build.sv $(LIBRARY) $(RANDOM)
	$(call build,)

producer.exe: producer.sv $(LIBRARY) $(RANDOM)
	$(call build,)

garage.exe: garage.sv $(LIBRARY) $(RANDOM) $(SUPPORT)/space_iterator.sv \
            $(SUPPORT)/deterministic_timeline.sv $(HOCON)
	$(call build,)

shop.exe: shop.sv $(LIBRARY) $(RANDOM) $(HOCON) shop_db.sv
	$(call build,-LDFLAGS -lsqlite3)

fixture.exe: fixture.sv $(LIBRARY) shop_db.sv
	$(call build,-LDFLAGS -lsqlite3)

viewer.exe: viewer.sv $(LIBRARY)
	$(call build,)

screen.exe: screen.sv viewer.exe $(LIBRARY) $(SUPPORT)/hwut_vterm.sv $(SUPPORT)/hwut_vterm_dpi.c \
            $(C_SUPPORT)/hwut_vterm.c $(HEADER)
	$(call build,-LDFLAGS "-ldl -lutil")

clean:
	rm -rf *.exe *.exe.obj

.PHONY: clean
