# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The C++ test applications, each built WHOLE from its source, the C++
# support modules it needs ('..') and the C modules they wrap ('../../c').
# The C modules are compiled as C, into a directory of the target's own
# ('<target>.o.d', removed after the link): no file is shared between two
# targets, so hwut may build several tests of this directory at once
# (services E-210: the build runs here, where this Makefile stands).
#______________________________________________________________________________
CXX      ?= g++
CC       ?= cc
CXXFLAGS ?= -std=c++17 -O1 -Wall -Wextra -Wno-unused-parameter
CFLAGS   ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT   = ..
C_SUPPORT = ../../c
HEADER    = $(wildcard $(SUPPORT)/*.hpp) $(wildcard $(C_SUPPORT)/*.h)
LIBRARY   = $(SUPPORT)/hwut_runner.cpp $(SUPPORT)/hwut_pytext.cpp \
            $(C_SUPPORT)/hwut_runner.c $(C_SUPPORT)/hwut_pytext.c

# $(call build,<libraries>): the C sources among the prerequisites compiled
# as C into '$@.o.d', then linked with the C++ sources among them.
define build
	rm -rf $@.o.d && mkdir $@.o.d
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) -c $$c -o $@.o.d/$$(basename $$c .c).o || exit 1; \
	done
	$(CXX) $(CXXFLAGS) -I$(SUPPORT) -o $@ $(filter %.cpp,$^) $@.o.d/*.o $(1) || { rm -rf $@.o.d; exit 1; }
	rm -rf $@.o.d
endef

test-deterministic-random.exe: test-deterministic-random.cpp $(LIBRARY) \
	                       $(SUPPORT)/deterministic_random.cpp $(C_SUPPORT)/deterministic_random.c $(HEADER)
	$(call build,-lm)

test-deterministic-timeline.exe: test-deterministic-timeline.cpp $(LIBRARY) \
	                         $(SUPPORT)/deterministic_timeline.cpp $(C_SUPPORT)/deterministic_timeline.c $(HEADER)
	$(call build,-lm)

test-space-iterator.exe: test-space-iterator.cpp $(LIBRARY) $(C_SUPPORT)/space_iterator.c $(HEADER)
	$(call build,-lm)

test-hwut_fsm.exe: test-hwut_fsm.cpp $(LIBRARY) $(SUPPORT)/hwut_fsm.cpp $(C_SUPPORT)/hwut_fsm.c $(HEADER)
	$(call build,-lm)

test-hwut_hocon.exe: test-hwut_hocon.cpp $(LIBRARY) $(SUPPORT)/hwut_hocon.cpp $(C_SUPPORT)/hwut_hocon.c \
	             $(SUPPORT)/deterministic_random.cpp $(C_SUPPORT)/deterministic_random.c $(HEADER)
	$(call build,-lm)

test-hwut_vterm.exe: test-hwut_vterm.cpp $(LIBRARY) $(SUPPORT)/hwut_vterm.cpp $(C_SUPPORT)/hwut_vterm.c $(HEADER)
	$(call build,-lm -ldl -lutil)

clean:
	rm -rf *.exe *.o.d

.PHONY: clean
