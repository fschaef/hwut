#! /usr/bin/env bash
#______________________________________________________________________________
# A TERMINAL FILE VIEWER -- the program 'screen.sh' tests; no test itself.
# 'viewer.py' of the Python demonstration, in bash.
#
#     viewer.sh <file>
#
# Full screen, on the terminal's alternate screen: a title bar (reverse
# video), as many lines of the file as fit, and a status line: the keys
# flush left, the lines shown flush right. Keys: 'j' or down one line
# further, 'k' or up one line back, 'q' quits. The terminal is put raw by
# 'stty'; a whole screen is ONE write, as Python's flush.
#______________________________________________________________________________

draw() {
    #  RETURN: 0; the whole screen is drawn with the file's line '$1' first
    #          ('line_list', 'name', 'row_n', 'column_n' the viewer's).
    local top=$1 body_n=$(( row_n - 2 )) out title where keys="j k q" i shown_n
    local -a shown=("${line_list[@]:top:body_n}")
    shown_n=${#shown[@]}
    printf -v title '%-*s' "$column_n" " $name"
    out=$'\e[H\e[2J\e[7m'"${title:0:column_n}"$'\e[0m\r\n'
    for (( i = 0; i < shown_n; ++i )); do out+="${shown[i]:0:column_n}"$'\r\n'; done
    for (( i = shown_n; i < body_n; ++i )); do out+=$'\r\n'; done
    printf -v where '%*s' $(( column_n - 1 - ${#keys} )) \
                    "lines $(( top + 1 ))-$(( top + shown_n )) of ${#line_list[@]}"
    out+=$'\e['"$row_n;1H$keys$where"
    printf '%s' "$out"
}

main() {
    #  RETURN: 0, once 'q' was pressed.
    local saved top=0 key rest max
    mapfile -t line_list < "$1"
    name=${1##*/}
    read -r row_n column_n < <(stty size)
    saved=$(stty -g)
    stty raw -echo
    printf '\e[?1049h'
    max=$(( ${#line_list[@]} - (row_n - 2) )); (( max < 0 )) && max=0
    while :; do
        draw "$top"
        IFS= read -rsN1 key || break
        if [[ $key == $'\e' ]]; then
            IFS= read -rsN2 -t 0.05 rest; key+=$rest
        fi
        case $key in
            q)         break ;;
            j|$'\e[B') (( top = top + 1 < max ? top + 1 : max )) ;;
            k|$'\e[A') (( top = top - 1 > 0 ? top - 1 : 0 )) ;;
        esac
    done
    printf '\e[?1049l'
    stty "$saved"
    return 0
}

main "$1"
