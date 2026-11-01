# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S PROGRAMS, each built WHOLE from its source and the
# support modules it needs. hwut builds a test where this Makefile stands
# (services E-210), several tests at once: no object file is shared between
# two targets.
#
#     demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe
#                       the tests -- hwut builds each by its header's 'build'
#     viewer.exe        the program 'screen.exe' runs: built with it
#     fixture.exe producer.exe
#                       helpers -- 'on_entry' in 'hwut.conf' builds them,
#                       and 'shop.exe' that 'delivery.json' is executed by
#
# WHERE THE C TEST SUPPORT STANDS is said on the ONE line below: the variable
# HWUT_SUPPORT_C, where the environment sets it; the clone's port else.
#______________________________________________________________________________
HWUT_SUPPORT_C ?= ../../../test_writing/c    # HWUT-SUPPORT-PATH
CC      ?= cc
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT  = $(strip $(HWUT_SUPPORT_C))
HEADER   = $(wildcard $(SUPPORT)/*.h)
RUNNER   = $(SUPPORT)/hwut_runner.c $(SUPPORT)/hwut_pytext.c
COMPILE  = $(CC) $(CFLAGS) -I$(SUPPORT) -o $@

demo.exe: demo.c
	$(COMPILE) $< -lpthread -lm

chamber.exe: chamber.c $(SUPPORT)/hwut_pytext.c $(HEADER)
	$(COMPILE) $< $(SUPPORT)/hwut_pytext.c -lm

door.exe: door.c
	$(COMPILE) $<

build.exe: build.c
	$(COMPILE) $< -lpthread

producer.exe: producer.c
	$(COMPILE) $< -lpthread

garage.exe: garage.c $(RUNNER) $(SUPPORT)/space_iterator.c $(SUPPORT)/hwut_hocon.c \
            $(SUPPORT)/deterministic_random.c $(SUPPORT)/deterministic_timeline.c $(HEADER)
	$(COMPILE) $< $(RUNNER) $(SUPPORT)/space_iterator.c $(SUPPORT)/hwut_hocon.c \
	           $(SUPPORT)/deterministic_random.c $(SUPPORT)/deterministic_timeline.c -lm

shop.exe: shop.c
	$(COMPILE) $< -lsqlite3 -lpthread

fixture.exe: fixture.c
	$(COMPILE) $< -lsqlite3

viewer.exe: viewer.c
	$(COMPILE) $<

screen.exe: screen.c viewer.exe $(SUPPORT)/hwut_vterm.c $(HEADER)
	$(COMPILE) $< $(SUPPORT)/hwut_vterm.c -lm -ldl -lutil

clean:
	rm -f *.exe

.PHONY: clean
