# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The Fortran test applications, each built WHOLE from its source and the
# support modules it needs ('..'), in the order a module is used after it is
# compiled. What the compiler writes besides the executable -- the '.mod'
# files ('-J') and, for 'test-hwut_vterm', the object of the C module it binds
# ('../../c/hwut_vterm.c') -- goes into a directory of the target's own
# ('<target>.d', removed after the link): no file is shared between two
# targets, so hwut may build several tests of this directory at once
# (services E-210: the build runs here, where this Makefile stands).
#
# '%.cov.exe' is the coverage-capable build hwut-root.conf names for Fortran
# ('coverage_target'): the same, compiled with '--coverage'.
#______________________________________________________________________________
FC      ?= gfortran
ifeq ($(origin FC),default)
FC      = gfortran
endif
CC      ?= cc
FFLAGS  ?= -std=f2018 -O1 -Wall -Wno-unused-dummy-argument -Wno-maybe-uninitialized
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT   = ..
C_SUPPORT = ../../c
# IN THE ORDER OF COMPILATION: a module after the modules it uses.
BASE      = $(SUPPORT)/hwut_text.f90 $(SUPPORT)/hwut_posix.f90 $(SUPPORT)/hwut_pytext.f90 \
            $(SUPPORT)/hwut_runner.f90

# $(call build,<extra flags>): the Fortran sources among the prerequisites
# compiled in order and linked with the C sources among them, which are
# compiled as C first; everything but the executable lives in '$@.d'.
define build
	rm -rf $@.d && mkdir $@.d
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) $(1) -I$(C_SUPPORT) -c $$c -o $@.d/$$(basename $$c .c).o || { rm -rf $@.d; exit 1; }; \
	done
	$(FC) $(FFLAGS) $(1) -J$@.d -o $@ $(filter %.f90,$^) $(patsubst %.c,$@.d/%.o,$(notdir $(filter %.c,$^))) $(2) || { rm -rf $@.d; exit 1; }
	rm -rf $@.d
endef

RANDOM   = $(BASE) $(SUPPORT)/deterministic_random.f90
TIMELINE = $(BASE) $(SUPPORT)/deterministic_timeline.f90
SPACE    = $(BASE) $(SUPPORT)/space_iterator.f90
FSM      = $(BASE) $(SUPPORT)/hwut_fsm.f90
HOCON    = $(BASE) $(SUPPORT)/deterministic_random.f90 $(SUPPORT)/hwut_hocon.f90
VTERM    = $(BASE) $(SUPPORT)/hwut_vterm.f90 $(C_SUPPORT)/hwut_vterm.c
VTERM_LIBRARY = -ldl -lutil

test-deterministic-random.exe:   $(RANDOM)   test-deterministic-random.f90
	$(call build)
test-deterministic-timeline.exe: $(TIMELINE) test-deterministic-timeline.f90
	$(call build)
test-space-iterator.exe:         $(SPACE)    test-space-iterator.f90
	$(call build)
test-hwut_fsm.exe:               $(FSM)      test-hwut_fsm.f90
	$(call build)
test-hwut_hocon.exe:             $(HOCON)    test-hwut_hocon.f90
	$(call build)
test-hwut_vterm.exe:             $(VTERM)    test-hwut_vterm.f90 $(C_SUPPORT)/hwut_vterm.h
	$(call build,,$(VTERM_LIBRARY))

test-deterministic-random.cov.exe:   $(RANDOM)   test-deterministic-random.f90
	$(call build,--coverage)
test-deterministic-timeline.cov.exe: $(TIMELINE) test-deterministic-timeline.f90
	$(call build,--coverage)
test-space-iterator.cov.exe:         $(SPACE)    test-space-iterator.f90
	$(call build,--coverage)
test-hwut_fsm.cov.exe:               $(FSM)      test-hwut_fsm.f90
	$(call build,--coverage)
test-hwut_hocon.cov.exe:             $(HOCON)    test-hwut_hocon.f90
	$(call build,--coverage)
test-hwut_vterm.cov.exe:             $(VTERM)    test-hwut_vterm.f90 $(C_SUPPORT)/hwut_vterm.h
	$(call build,--coverage,$(VTERM_LIBRARY))

clean:
	rm -rf *.exe *.d *.gcda *.gcno

.PHONY: clean
