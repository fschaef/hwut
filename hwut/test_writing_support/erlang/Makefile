# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# WHAT THE ERLANG TEST SUPPORT BUILDS: every module '*.erl' here into
# 'ebin/*.beam', and 'hwut_vterm_port' -- the C port's 'hwut_vterm.c',
# unchanged, behind an Erlang port ('hwut_vterm_port.c'). Nothing is
# installed; a test escript runs 'make' here when a module is missing or
# older than its source ('hwut_boot.hrl'), 'hwut_vterm' when the port
# program is.
#
# SEVERAL TESTS MAY BUILD AT ONCE: each product is written under a name of
# its own process and then renamed onto its target -- a rename is atomic,
# so no test ever loads a half-written module or starts a half-written
# program.
#______________________________________________________________________________
ERLC    ?= erlc
CC      ?= cc
CFLAGS  ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
C_PORT   = ../c
BEAM     = $(patsubst %.erl,ebin/%.beam,$(wildcard *.erl))

all: $(BEAM)

ebin/%.beam: %.erl $(wildcard *.hrl)
	@mkdir -p ebin
	@d=ebin/.build.$$$$; mkdir -p $$d && $(ERLC) -o $$d $< && mv -f $$d/$*.beam $@; s=$$?; rm -rf $$d; exit $$s

hwut_vterm_port: hwut_vterm_port.c $(C_PORT)/hwut_vterm.c $(C_PORT)/hwut_vterm.h
	$(CC) $(CFLAGS) -I$(C_PORT) -o $@.$$$$ hwut_vterm_port.c $(C_PORT)/hwut_vterm.c -lm -ldl -lutil \
	&& mv -f $@.$$$$ $@

clean:
	rm -rf ebin hwut_vterm_port hwut_vterm_port.*[0-9]

.PHONY: all clean
