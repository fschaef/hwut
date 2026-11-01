# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S PROGRAMS. GHDL's mcode backend writes no executable:
# 'x.exe' is a LAUNCHER ('demo_launch.sh') that runs the design analysed into
# 'x.work', a directory of the target's own that also holds 'libhwut_vhdl.so'
# -- the port's VHPIDIRECT glue, the C modules it wraps and 'demo_vhpi.c',
# compiled for this target alone. No file is shared between two targets:
# hwut builds a test where this Makefile stands (services E-210), several at
# once.
#
#     demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe
#                       the tests -- hwut builds each by its header's 'build'
#     viewer.exe        the program 'screen.exe' runs: built with it
#     fixture.exe producer.exe
#                       helpers -- 'on_entry' in 'hwut.conf' builds them, and
#                       'shop.exe', which 'delivery.json' is executed by
#
# WHERE THE VHDL TEST SUPPORT STANDS is said on the ONE line below: the
# variable HWUT_SUPPORT_VHDL, where the environment sets it; else the path
# after '?='. The C modules it wraps stand beside it, in '../c'.
#______________________________________________________________________________
HWUT_SUPPORT_VHDL ?= ../../../test_writing/vhdl    # HWUT-SUPPORT-PATH
GHDL      ?= ghdl
GHDLFLAGS ?= --std=08
CC        ?= cc
CFLAGS    ?= -std=c99 -O1 -Wall -Wextra -Wno-unused-parameter
SUPPORT    = $(strip $(HWUT_SUPPORT_VHDL))
C_SUPPORT  = $(SUPPORT)/../c
# IN THE ORDER OF ANALYSIS: a package after the packages it uses.
PACKAGE    = $(SUPPORT)/hwut_vhpi.vhd $(SUPPORT)/hwut_pytext.vhd $(SUPPORT)/hwut_runner.vhd \
             $(SUPPORT)/deterministic_random.vhd $(SUPPORT)/deterministic_timeline.vhd \
             $(SUPPORT)/space_iterator.vhd $(SUPPORT)/hwut_fsm.vhd $(SUPPORT)/hwut_hocon.vhd \
             $(SUPPORT)/hwut_vterm.vhd demo_vhpi.vhd
GLUE       = $(SUPPORT)/hwut_vhpi.c $(C_SUPPORT)/hwut_pytext.c $(C_SUPPORT)/hwut_fsm.c \
             $(C_SUPPORT)/hwut_hocon.c $(C_SUPPORT)/hwut_vterm.c demo_vhpi.c
HEADER     = $(wildcard $(C_SUPPORT)/*.h)

# The shop and its fixture keep their stock in SQLite.
shop.exe fixture.exe: SQL_VHD = demo_sql.vhd
shop.exe fixture.exe: SQL_C   = -DDEMO_SQLITE
shop.exe fixture.exe: SQL_LIB = -lsqlite3
shop.exe fixture.exe: demo_sql.vhd

# 'screen.exe' runs 'viewer.exe' on a pseudo-terminal.
screen.exe: viewer.exe

# x.exe: x.vhd, entity 'x'.
%.exe: %.vhd $(PACKAGE) $(GLUE) $(HEADER) demo_launch.sh
	rm -rf $*.work && mkdir $*.work
	$(CC) $(CFLAGS) $(SQL_C) -fPIC -shared -I$(C_SUPPORT) -o $*.work/libhwut_vhdl.so $(GLUE) \
	      -lm -ldl -lutil $(SQL_LIB)
	$(GHDL) -a $(GHDLFLAGS) --workdir=$*.work $(PACKAGE) $(SQL_VHD) $<
	printf '#! /bin/sh\nexec sh "$$(dirname "$$0")/demo_launch.sh" %s "$$@"\n' "$*" > $@.tmp
	chmod +x $@.tmp && mv $@.tmp $@

all: demo.exe chamber.exe door.exe garage.exe build.exe shop.exe screen.exe fixture.exe producer.exe

clean:
	rm -rf *.exe *.exe.tmp *.work stock.csv

.PHONY: all clean
