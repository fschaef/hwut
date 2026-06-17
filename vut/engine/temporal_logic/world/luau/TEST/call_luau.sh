#!/bin/sh
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# PURPOSE: shebang/launcher wrapper so HWUT's call convention reaches Luau.
script=$1; shift
exec luau "$script" -a "$@"
