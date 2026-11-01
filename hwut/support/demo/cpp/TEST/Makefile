# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The demonstration's C++ applications, each built WHOLE from its source and,
# where it uses hwut's test support, the C++ support sources it needs and the
# C modules they wrap. hwut runs this Makefile HERE (services E-210), one
# 'make <stem>.exe' per test, several at once: no file is shared between two
# targets -- a target's C objects go to '<target>.o.d', removed after the
# link.
#
# WHERE THE SUPPORT STANDS is said on the ONE line marked below: the variable
# HWUT_SUPPORT_CPP, where the environment sets it, else the port in this
# clone. The C modules stand beside it, in '../c' of it (the C++ port wraps
# them; README.txt, MAKE IT IMPORTABLE).
#______________________________________________________________________________
HWUT_SUPPORT_CPP ?= ../../../test_writing/cpp# HWUT-SUPPORT-PATH
SUPPORT   = $(strip $(HWUT_SUPPORT_CPP))
C_SUPPORT = $(SUPPORT)/../c

CXX      ?= g++
CC       ?= cc
CXXFLAGS ?= -std=c++17 -O1 -Wall -Wextra -Wno-unused-parameter
CFLAGS   ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
RUNNER    = $(SUPPORT)/hwut_runner.cpp $(SUPPORT)/hwut_pytext.cpp \
            $(C_SUPPORT)/hwut_runner.c $(C_SUPPORT)/hwut_pytext.c

# $(call build,<libraries>): the C sources among the prerequisites compiled
# as C into '$@.o.d', then linked with the C++ sources among them.
define build
	rm -rf $@.o.d && mkdir $@.o.d
	for c in $(filter %.c,$^); do \
	    $(CC) $(CFLAGS) -c $$c -o $@.o.d/$$(basename $$c .c).o || { rm -rf $@.o.d; exit 1; }; \
	done
	$(CXX) $(CXXFLAGS) -I$(SUPPORT) -o $@ $(filter %.cpp,$^) $$(ls $@.o.d/*.o 2>/dev/null) $(1) || { rm -rf $@.o.d; exit 1; }
	rm -rf $@.o.d
endef

#  NO SUPPORT: the application alone.
demo.exe chamber.exe door.exe build.exe protocol.exe viewer.exe: %.exe: %.cpp
	$(call build,-pthread)

#  THE SHOP: SQLite. 'delivery.exe' is 'shop.cpp' again, a target of its own
#  for the header-less test 'delivery.json' (hwut.conf, 'apps'); 'fixture.exe'
#  is built by 'on_entry'.
shop.exe delivery.exe: shop.cpp
	$(call build,-pthread -lsqlite3)

fixture.exe: fixture.cpp
	$(call build,-lsqlite3)

garage.exe: garage.cpp $(RUNNER) \
            $(SUPPORT)/hwut_hocon.cpp $(C_SUPPORT)/hwut_hocon.c \
            $(SUPPORT)/deterministic_random.cpp $(C_SUPPORT)/deterministic_random.c \
            $(SUPPORT)/deterministic_timeline.cpp $(C_SUPPORT)/deterministic_timeline.c \
            $(C_SUPPORT)/space_iterator.c
	$(call build,-lm)

#  'viewer.exe' is the program the screen test runs: built with it, by it alone.
screen.exe: screen.cpp $(SUPPORT)/hwut_vterm.cpp $(C_SUPPORT)/hwut_vterm.c | viewer.exe
	$(call build,-lm -ldl -lutil)

clean:
	rm -rf *.exe *.o.d

.PHONY: clean
