# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S PROGRAMS, each built WHOLE from its source and the
# support modules it needs, a module after the modules it uses. hwut builds a
# test where this Makefile stands (services E-210), several tests at once:
# what the compiler writes besides the executable -- the '.mod' files ('-J')
# and the objects of C sources -- goes into a directory of the target's own
# ('<target>.d', removed after the link). No file is shared between targets.
#
#     demo chamber door build garage shop screen
#                       the tests -- hwut builds '<stem>.exe' by the header's
#                       'build'; '<stem>.cov.exe' is the same with
#                       '--coverage' (hwut-root.conf's 'coverage_target')
#     viewer            the program 'screen.exe' runs
#     fixture producer  helpers -- 'on_entry' in 'hwut.conf' builds them, and
#                       'shop.exe', which 'delivery.json' is executed by, and
#                       'viewer.exe'
#
# WHERE THE FORTRAN TEST SUPPORT STANDS is said on the ONE line marked below:
# the variable HWUT_SUPPORT_FORTRAN, where the environment sets it (Fortran
# has no search path of its own for sources: a test compiles the support's
# modules with itself); the clone's port else. 'hwut_vterm' binds the C
# port's 'hwut_vterm.c': beside the Fortran port where it stands there, else
# in the hwut that runs this ('import hwut').
#______________________________________________________________________________
HWUT_SUPPORT_FORTRAN ?= ../../../test_writing/fortran# HWUT-SUPPORT-PATH
SUPPORT   := $(strip $(HWUT_SUPPORT_FORTRAN))
C_SUPPORT := $(or $(patsubst %/hwut_vterm.c,%,$(wildcard $(SUPPORT)/../c/hwut_vterm.c)),$(shell \
               python3 -c "import hwut, os; print(os.path.join(list(hwut.__path__)[0], 'support', 'test_writing', 'c'))" 2>/dev/null))

FC      ?= gfortran
ifeq ($(origin FC),default)
FC      = gfortran
endif
CC      ?= cc
FFLAGS  ?= -std=f2018 -O1 -Wall -Wno-unused-dummy-argument -Wno-maybe-uninitialized
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
OPENMP   = -fopenmp

# THE SUPPORT, in the order of compilation.
TEXT     = $(SUPPORT)/hwut_text.f90
POSIX    = $(TEXT) $(SUPPORT)/hwut_posix.f90
RUNNER   = $(POSIX) $(SUPPORT)/hwut_pytext.f90 $(SUPPORT)/hwut_runner.f90
GENERATE = $(RUNNER) $(SUPPORT)/space_iterator.f90 $(SUPPORT)/deterministic_random.f90 \
           $(SUPPORT)/hwut_hocon.f90 $(SUPPORT)/deterministic_timeline.f90
VTERM    = $(POSIX) $(SUPPORT)/hwut_vterm.f90 $(C_SUPPORT)/hwut_vterm.c

# WHAT EACH PROGRAM IS MADE OF: '<stem>_SOURCES', and where it wants more,
# '<stem>_FLAGS' (compile and link) and '<stem>_LIBS' (link).
demo_SOURCES     = $(POSIX) demo.f90
demo_FLAGS       = $(OPENMP)
chamber_SOURCES  = $(TEXT) chamber.f90
door_SOURCES     = $(TEXT) door.f90
build_SOURCES    = $(POSIX) build.f90
build_FLAGS      = $(OPENMP)
producer_SOURCES = $(POSIX) producer.f90
producer_FLAGS   = $(OPENMP)
garage_SOURCES   = $(GENERATE) garage.f90
shop_SOURCES     = $(POSIX) shop_db.f90 shop.f90
shop_FLAGS       = $(OPENMP)
shop_LIBS        = -lsqlite3
fixture_SOURCES  = $(POSIX) shop_db.f90 fixture.f90
fixture_LIBS     = -lsqlite3
viewer_SOURCES   = $(POSIX) viewer.f90
screen_SOURCES   = $(VTERM) screen.f90
screen_LIBS      = -ldl -lutil

# $(call build,<flags>,<libraries>): the Fortran sources among the
# prerequisites compiled in order, linked with the C sources among them,
# which are compiled as C first; everything but the executable in '$@.d'.
define build
	rm -rf $@.d && mkdir $@.d
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) $(1) -I$(C_SUPPORT) -c $$c -o $@.d/$$(basename $$c .c).o || { rm -rf $@.d; exit 1; }; \
	done
	$(FC) $(FFLAGS) $(1) -J$@.d -o $@ $(filter %.f90,$^) $(patsubst %.c,$@.d/%.o,$(notdir $(filter %.c,$^))) $(2) \
	    || { rm -rf $@.d; exit 1; }
	rm -rf $@.d
endef

.SECONDEXPANSION:
%.cov.exe: $$($$*_SOURCES)
	$(call build,--coverage $($*_FLAGS),$($*_LIBS))
%.exe: $$($$*_SOURCES)
	$(call build,$($*_FLAGS),$($*_LIBS))

# 'screen.exe' runs 'viewer.exe': built with it.
screen.exe screen.cov.exe: viewer.exe

clean:
	rm -rf *.exe *.d *.gcda *.gcno stock.csv

.PHONY: clean
