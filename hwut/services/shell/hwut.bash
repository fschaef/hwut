# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
# TAB COMPLETION OF THE HWUT FACES, bash (services E-151).
#     source <this file>          in '~/.bashrc'
# The line up to the cursor goes to the completer whole; it answers one
# candidate per line, already cut at bash's word break. A face is every
# 'hwut' and 'hwut.*' command on PATH when this file is read.
_hwut_complete() {
    local IFS=$'\n'
    COMPREPLY=($(hwut --command-line-complete bash "${COMP_LINE:0:COMP_POINT}" 2>/dev/null))
    #  A directory is a step, not an end: no blank after it.
    if [ ${#COMPREPLY[@]} -eq 1 ] && [ "${COMPREPLY[0]%/}" != "${COMPREPLY[0]}" ]; then
        compopt -o nospace 2>/dev/null
    fi
}
_hwut_faces=$(compgen -c hwut | grep -E '^hwut(\.|$)' | sort -u)
[ -n "$_hwut_faces" ] && complete -F _hwut_complete $_hwut_faces
unset _hwut_faces
