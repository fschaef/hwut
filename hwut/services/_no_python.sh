#! /bin/sh
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# THE URGENCY REPORT WHERE NO PYTHON STANDS (services E-224): a shim of
# 'bin/' calls this, instead of 'python3', when 'python3' is not on PATH.
# The block is 'lib/system_report.py''s in its keys; the values are what
# a shell can read. Status 127, the shell's own for a command not found.
#
#     _no_python.sh <face>
face=$1
os="unknown system"
if [ -r /etc/os-release ]; then
    os=$(sed -n 's/^PRETTY_NAME="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' /etc/os-release)
fi
os="$os ($(uname -s) $(uname -r), $(uname -m))"
HERE=$(dirname "$(readlink -f "$0")")
where=$(cd "$HERE/.." && pwd)
case "$where" in "$HOME"/*) where="~${where#"$HOME"}" ;; esac
{
    echo "$face cannot run: the program 'python3' is not on PATH."
    echo
    echo "<hwut-system>"
    echo "face:     $face"
    echo "problem:  the program 'python3' is not on PATH"
    echo "os:       $os"
    echo "python:   absent"
    echo "hwut:     $where (clone)"
    echo "PATH:     $(printf "%s" "$PATH" | sed "s|$HOME|~|g")"
    echo "missing:  program python3 (absent) apt: python3"
    echo "</hwut-system>"
    echo
    echo "Pass the lines from <hwut-system> to </hwut-system> to your AI assistant: they say what this machine is and what went wrong on it."
} >&2
exit 127
