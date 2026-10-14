#! /bin/sh
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
# The launcher of 'hwut.move': 'services/move.py' run as a module,
# from wherever 'hwut.move' is called, by PATH or by path.
HERE=$(dirname "$(readlink -f "$0")")
PYTHONPATH="$HERE/../..${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -m hwut.services.move "$@"
