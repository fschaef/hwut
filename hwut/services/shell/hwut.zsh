# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
# TAB COMPLETION OF THE HWUT FACES, zsh (services E-151).
#     source <this file>          in '~/.zshrc', after 'compinit'
# The line up to the cursor goes to the completer whole; it answers one
# 'candidate:description' per line, ':' in a candidate escaped. A face is
# every 'hwut' and 'hwut.*' command on PATH when this file is read.
_hwut_complete() {
    local -a line_list dir_list other_list
    local line
    line_list=("${(@f)$(hwut --command-line-complete zsh "$LBUFFER" 2>/dev/null)}")
    for line in $line_list; do
        [[ -z $line ]] && continue
        #  A directory is a step, not an end: no blank after it.
        if [[ $line == */ ]]; then dir_list+=("${line//\\:/:}")
        else                       other_list+=("$line")
        fi
    done
    (( $#dir_list ))   && compadd -S '' -- $dir_list
    (( $#other_list )) && _describe -t hwut-words 'hwut' other_list
    return 0
}
if (( $+functions[compdef] )); then
    compdef _hwut_complete ${(k)commands[(I)hwut]} ${(k)commands[(I)hwut.*]}
fi
