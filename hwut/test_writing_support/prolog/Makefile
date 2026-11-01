# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE ONE COMPILED PIECE OF THE PROLOG TEST SUPPORT: 'hwut_vterm4pl.so', the
# foreign library through which 'hwut_vterm.pro' reaches libvterm and the
# pseudo-terminal -- the C port's 'hwut_vterm.c', unchanged, and the glue
# 'hwut_vterm4pl.c' written against SWI-Prolog's 'SWI-Prolog.h' (in the
# 'include' directory of the installation, which 'swipl' itself names).
# 'hwut_vterm.pro' runs 'make' here on first use; nothing else needs
# building. ONE 'cc' CALL compiles and links -- no object file is left
# beside a source ('swipl-ld' would write '../c/hwut_vterm.o': another
# port's directory, and a name two builds would share).
#
# SEVERAL TESTS MAY BUILD IT AT ONCE: the library is linked under a name of
# its own process ('$@.<pid>.so') and then renamed onto '$@' -- a rename is
# atomic, so no test ever loads a half-written library.
#______________________________________________________________________________
CC      ?= cc
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SWIPL   ?= swipl
PLBASE  := $(shell $(SWIPL) --dump-runtime-variables | sed -n 's/^PLBASE="\(.*\)";$$/\1/p')
C_PORT   = ../c

hwut_vterm4pl.so: hwut_vterm4pl.c $(C_PORT)/hwut_vterm.c $(C_PORT)/hwut_vterm.h
	$(CC) $(CFLAGS) -shared -fPIC -I$(PLBASE)/include -I$(C_PORT) -o $@.$$$$.so \
	      hwut_vterm4pl.c $(C_PORT)/hwut_vterm.c -ldl -lutil -lm \
	&& mv -f $@.$$$$.so $@

clean:
	rm -f hwut_vterm4pl.so hwut_vterm4pl.so.*.so

.PHONY: clean
