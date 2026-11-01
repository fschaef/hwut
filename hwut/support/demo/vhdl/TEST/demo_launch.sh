#! /bin/sh
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE LAUNCHER OF A DEMONSTRATION PROGRAM: 'x.exe' (written by 'Makefile')
# calls it as
#
#     demo_launch.sh <entity> [<argument> [<argument>]]
#
# and it runs the entity's simulation (GHDL), analysed into 'x.work' beside
# this file, with the command line as generics -- VHDL reads no argv:
# HWUT_ARGC the number of arguments, HWUT_ARGV1 the first (the runner's
# two, as the port's 'hwut_launch.sh' gives them), HERE this directory.
# EVERY argument stands in the environment as well, 'HWUT_ARGV', each ended
# by a newline -- a generic takes no control character, and an empty one
# GHDL 4.1 does not take at all ('-gX=' fails): an empty first argument is
# left to the generic's default, "". 'x.work' holds 'libhwut_vhdl.so', which
# GHDL loads for the VHPIDIRECT subprograms, found along LD_LIBRARY_PATH.
#
# RETURN: the exit status of the simulation -- the program's own.
#______________________________________________________________________________
here=$(cd "$(dirname "$0")" && pwd)
entity=$1
shift
work="$here/$entity.work"
LD_LIBRARY_PATH="$work${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
HWUT_ARGV=
for argument in "$@"; do HWUT_ARGV="$HWUT_ARGV$argument
"; done
export LD_LIBRARY_PATH HWUT_ARGV
if [ -z "$1" ]; then
    exec ${GHDL:-ghdl} -r --std=08 --workdir="$work" "$entity" "-gHERE=$here" "-gHWUT_ARGC=$#"
fi
exec ${GHDL:-ghdl} -r --std=08 --workdir="$work" "$entity" "-gHERE=$here" "-gHWUT_ARGC=$#" "-gHWUT_ARGV1=$1"
