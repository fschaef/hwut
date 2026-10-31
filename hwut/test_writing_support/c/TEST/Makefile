# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The C test applications, each built WHOLE from its source and the support
# modules it needs: no object file is shared between two targets, so hwut
# may build several tests of this directory at once (services E-210: the
# build runs here, where this Makefile stands).
#______________________________________________________________________________
CC     ?= cc
CFLAGS ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT = ..
LIBRARY = $(SUPPORT)/hwut_runner.c $(SUPPORT)/hwut_pytext.c
HEADER  = $(wildcard $(SUPPORT)/*.h)

test-deterministic-random.exe: test-deterministic-random.c $(LIBRARY) $(SUPPORT)/deterministic_random.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/deterministic_random.c -lm

test-deterministic-timeline.exe: test-deterministic-timeline.c $(LIBRARY) $(SUPPORT)/deterministic_timeline.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/deterministic_timeline.c -lm

test-space-iterator.exe: test-space-iterator.c $(LIBRARY) $(SUPPORT)/space_iterator.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/space_iterator.c -lm

test-hwut_fsm.exe: test-hwut_fsm.c $(LIBRARY) $(SUPPORT)/hwut_fsm.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/hwut_fsm.c -lm

test-hwut_hocon.exe: test-hwut_hocon.c $(LIBRARY) $(SUPPORT)/hwut_hocon.c $(SUPPORT)/deterministic_random.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/hwut_hocon.c $(SUPPORT)/deterministic_random.c -lm

test-hwut_vterm.exe: test-hwut_vterm.c $(LIBRARY) $(SUPPORT)/hwut_vterm.c $(HEADER)
	$(CC) $(CFLAGS) -I$(SUPPORT) -o $@ $< $(LIBRARY) $(SUPPORT)/hwut_vterm.c -lm -ldl -lutil

clean:
	rm -f *.exe

.PHONY: clean
