# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE ONE COMPILED PIECE OF THIS DIRECTORY: 'shop_db4pl.so', the foreign
# library through which 'shop_db.pro' reaches SQLite ('libsqlite3.so.0',
# loaded at run time by 'dlopen' -- no header of SQLite is needed), written
# against SWI-Prolog's 'SWI-Prolog.h' (in the 'include' directory of the
# installation, which 'swipl' itself names). 'shop_db.pro' runs 'make' here
# when it is loaded -- by 'fixture.pro' at 'on_entry', before any test.
# No test declares a build: what hwut runs is 'swipl <file>.pro'.
#
# ONE 'cc' CALL compiles and links -- no object file is left beside the
# source. SEVERAL PROCESSES MAY BUILD AT ONCE: the library is linked under a
# name of its own process ('$@.<pid>.so') and then renamed onto '$@' -- a
# rename is atomic, so nobody ever loads a half-written library.
#______________________________________________________________________________
CC      ?= cc
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra
SWIPL   ?= swipl
PLBASE  := $(shell $(SWIPL) --dump-runtime-variables | sed -n 's/^PLBASE="\(.*\)";$$/\1/p')

shop_db4pl.so: shop_db4pl.c
	$(CC) $(CFLAGS) -shared -fPIC -I$(PLBASE)/include -o $@.$$$$.so shop_db4pl.c -ldl \
	&& mv -f $@.$$$$.so $@

clean:
	rm -f shop_db4pl.so shop_db4pl.so.*.so

.PHONY: clean
