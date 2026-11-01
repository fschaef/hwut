# support.sh -- WHERE THE BASH TEST SUPPORT STANDS, said once for every test
# of this directory; no test itself ('ignore' in hwut.conf).
#
#     source "$(dirname "${BASH_SOURCE[0]}")/support.sh"
#     source hwut_runner.sh              # found on PATH, as bash finds it
#
# RETURN: 0; PATH ends in the bash port's directory, so that 'source
#         <module>.sh' finds the port's modules there -- bash's own search
#         ('shopt sourcepath'): a name without '/' is looked up on PATH.
# The port's place stands as a path relative to this directory, or an
# absolute one. It is APPENDED: a PATH that names the port already (a user's
# 'export PATH="<dir>/bash:$PATH"') is searched first and wins.
_demo_here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
_demo_port=../../../test_writing/bash; [[ $_demo_port == /* ]] || _demo_port=$_demo_here/$_demo_port; PATH="$PATH:$_demo_port"    # HWUT-SUPPORT-PATH
shopt -s sourcepath
