#! /bin/sh
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE LAUNCHER OF A VHDL TEST APPLICATION: 'test-x.exe' (written by
# 'TEST/Makefile') calls it as
#
#     hwut_launch.sh <work directory> <entity> [<argument>]
#
# and it runs the entity's simulation (GHDL) with the command line as the two
# generics a VHDL design can be given -- HWUT_ARGC, the number of arguments,
# and HWUT_ARGV1, the first -- since VHDL reads no argv. The work directory
# holds the analysed design and 'libhwut_vhdl.so', which GHDL loads for the
# VHPIDIRECT subprograms, found along LD_LIBRARY_PATH.
#
# RETURN: the exit status of the simulation -- the test's own (hwut_runner).
#______________________________________________________________________________
work=$1
entity=$2
shift 2
LD_LIBRARY_PATH="$work${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LD_LIBRARY_PATH
if [ $# -eq 0 ]; then
    exec ${GHDL:-ghdl} -r --std=08 --workdir="$work" "$entity" -gHWUT_ARGC=0
fi
exec ${GHDL:-ghdl} -r --std=08 --workdir="$work" "$entity" "-gHWUT_ARGC=$#" "-gHWUT_ARGV1=$1"
