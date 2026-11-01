# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE ONE COMPILED PIECE OF THE BASH TEST SUPPORT: 'hwut_vterm_server', the
# coprocess through which 'hwut_vterm.sh' reaches libvterm and the
# pseudo-terminal -- the C port's 'hwut_vterm.c', unchanged, behind a line
# protocol. 'hwut_vterm.sh' runs 'make' here on first use; nothing else needs
# building.
#
# SEVERAL TESTS MAY BUILD IT AT ONCE: the program is linked under a name of
# its own process ('$@.<pid>') and then renamed onto '$@' -- a rename is
# atomic, so no test ever starts a half-written program.
#______________________________________________________________________________
CC     ?= cc
CFLAGS ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
C_PORT  = ../c

hwut_vterm_server: hwut_vterm_server.c $(C_PORT)/hwut_vterm.c $(C_PORT)/hwut_vterm.h
	$(CC) $(CFLAGS) -I$(C_PORT) -o $@.$$$$ hwut_vterm_server.c $(C_PORT)/hwut_vterm.c -lm -ldl -lutil \
	&& mv -f $@.$$$$ $@

clean:
	rm -f hwut_vterm_server hwut_vterm_server.*[0-9]

.PHONY: clean
