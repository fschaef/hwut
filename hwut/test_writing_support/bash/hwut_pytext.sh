# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: TEXT AS PYTHON PRINTS IT -- so a bash test and a Python test of the
#          same module print the same bytes and share one GOOD file by a
#          '.link' (bookkeeper B-32). The bash twin of 'c/hwut_pytext.c'.
#
#     pytext_float_repr 0.1           REPLY='0.1'     the shortest text that
#     pytext_float_repr 1e-5          REPLY='1e-05'   reads back; exponential
#     pytext_float_repr 1e16          REPLY='1e+16'   below 1e-4, from 1e16 on
#     pytext_str_repr "it's"          REPLY="\"it's\""
#     pytext_bytes_repr $'\e[A'       REPLY="b'\\x1b[A'"
#     pytext_bool 1                   REPLY='True'    (0 or '' -> 'False')
#     pytext_list_repr  str a b       REPLY="['a', 'b']"   ('int': bare)
#     pytext_tuple_repr str a         REPLY="('a',)"
#     pytext_ljust "ä" 6              REPLY='ä     '  (Python's '%-6s':
#                                                     characters, not bytes)
#     pytext_sorted a_list            REPLY_LIST, sorted as Python sorts str
#
# A FUNCTION'S RESULT IS IN 'REPLY' (or 'REPLY_LIST'), never on stdout: a
# '$(...)' would cost a process per call. Text is handled as BYTES
# (LC_ALL=C inside), UTF-8 counted where Python counts characters.
#
# A FLOAT IS NO BASH VALUE: bash's arithmetic is 64-bit integer. A float is
# carried as its text and written, read and computed by 'awk' (POSIX; the
# platform's libm), whose 'PYTEXT_AWK' functions any module may prepend to
# its own awk program -- 'float_repr(x)', 'py_round(x)'.
#______________________________________________________________________________
[[ -n ${_HWUT_PYTEXT_SH:-} ]] && return 0
_HWUT_PYTEXT_SH=1

#  THE AWK FUNCTIONS: Python's 'repr(float)' and 'round(float)'.
PYTEXT_AWK='
function float_repr(x,    p, text, sign, digits, e, point, n, mantissa) {
    #  RETURN: the shortest decimal that reads back to "x", fixed notation
    #          where the decimal point falls in (-4, 16], exponential else.
    if (x != x)                 return "nan"
    if (x == 2^1024)            return "inf"
    if (x == -(2^1024))         return "-inf"
    if (x == 0)                 return (sprintf("%g", x) ~ /^-/) ? "-0.0" : "0.0"
    for (p = 0; p <= 16; ++p) {
        text = sprintf("%." p "e", x)
        if (text + 0 == x) break
    }
    sign = ""
    if (substr(text, 1, 1) == "-") { sign = "-"; text = substr(text, 2) }
    e      = substr(text, index(text, "e") + 1) + 0
    digits = substr(text, 1, index(text, "e") - 1)
    sub(/\./, "", digits)
    sub(/0+$/, "", digits)
    if (digits == "") digits = "0"
    point = e + 1
    n     = length(digits)
    if (point > -4 && point <= 16) {
        if (point <= 0) return sign "0." zeros(-point) digits
        if (point >= n) return sign digits zeros(point - n) ".0"
        return sign substr(digits, 1, point) "." substr(digits, point + 1)
    }
    mantissa = (n > 1) ? substr(digits, 1, 1) "." substr(digits, 2) : digits
    return sprintf("%s%se%s%02d", sign, mantissa, (e < 0) ? "-" : "+", (e < 0) ? -e : e)
}
function zeros(n,    s) { s = ""; while (n-- > 0) s = s "0"; return s }
function py_round(x,    f, d) {
    #  RETURN: "x" rounded as Python rounds -- to the nearest integer, a
    #          half to the EVEN one.
    f = int(x); if (f > x) f -= 1
    d = x - f
    if (d > 0.5) return f + 1
    if (d < 0.5) return f
    return (f % 2 == 0) ? f : f + 1
}
'

pytext_float_repr() {
    #  RETURN: 0, REPLY = the float the text '$1' spells (a decimal, or an
    #             awk expression such as '1/3') as Python's 'repr' writes it.
    REPLY=$(awk "$PYTEXT_AWK"' BEGIN { print float_repr(('"$1"') + 0) }')
}

pytext_bool() {
    #  RETURN: 0, REPLY = 'True' where '$1' is a non-empty text other than
    #             '0'; 'False' else.
    if [[ -n ${1:-} && $1 != 0 ]]; then REPLY=True; else REPLY=False; fi
}

_pytext_quoted() {
    #  RETURN: 0, REPLY = '$1' in the quotes Python's repr chooses -- single,
    #             or double where it holds a single quote and no double one
    #             -- the backslash, that quote and what does not print
    #             escaped. With '$2' = 1 (bytes) every byte from 0x7f on is
    #             escaped too; a str keeps non-ASCII characters as they
    #             stand.
    local LC_ALL=C
    local s=$1 bytes_f=${2:-0} quote="'" out="" c i n code
    [[ $s == *"'"* && $s != *'"'* ]] && quote='"'
    #  THE COMMON CASE AT ONCE: nothing in it to escape.
    if [[ $s != *[\\$quote$'\x01'-$'\x1f'$'\x7f'-$'\xff']* ]]; then
        REPLY=$quote$s$quote; return 0
    fi
    n=${#s}
    for (( i = 0; i < n; ++i )); do
        c=${s:i:1}
        case $c in
            \\)           out+='\\' ;;
            "$quote")     out+="\\$quote" ;;
            $'\n')        out+='\n' ;;
            $'\t')        out+='\t' ;;
            $'\r')        out+='\r' ;;
            [$'\x01'-$'\x1f'$'\x7f'])
                printf -v code '\\x%02x' "'$c"; out+=$code ;;
            [$'\x80'-$'\xff'])
                if (( bytes_f )); then printf -v code '\\x%02x' "'$c"; out+=$code
                else                   out+=$c
                fi ;;
            *)            out+=$c ;;
        esac
    done
    REPLY=$quote$out$quote
}

pytext_str_repr() {
    #  RETURN: 0, REPLY = the text '$1' as Python's 'repr(str)' writes it.
    _pytext_quoted "$1" 0
}

pytext_bytes_repr() {
    #  RETURN: 0, REPLY = the bytes '$1' as Python's 'repr(bytes)' writes
    #             them -- "b'\x1b[A'": printable ASCII as it stands, '\t',
    #             '\n', '\r', every other byte as '\xNN'.
    _pytext_quoted "$1" 1
    REPLY=b$REPLY
}

pytext_list_repr() {
    #  RETURN: 0, REPLY = the values '$2...' as Python prints a list --
    #             '[a, b]'; with '$1' = 'str' each one quoted as repr quotes
    #             a str, with '$1' = 'int' (or anything else) bare.
    local kind=$1 out="" item; shift
    for item in "$@"; do
        if [[ $kind == str ]]; then pytext_str_repr "$item"; item=$REPLY; fi
        out+="${out:+, }$item"
    done
    REPLY="[$out]"
}

pytext_tuple_repr() {
    #  RETURN: 0, REPLY = the values '$2...' as Python prints a tuple --
    #             '()', "('a',)" for one (the comma Python writes),
    #             "('a', 'b')"; quoted where '$1' = 'str'.
    local kind=$1; shift
    pytext_list_repr "$kind" "$@"
    if (( $# == 1 )); then REPLY="(${REPLY:1:${#REPLY}-2},)"
    else                   REPLY="(${REPLY:1:${#REPLY}-2})"
    fi
}

pytext_char_n() {
    #  RETURN: 0, REPLY = how many characters the UTF-8 text '$1' holds --
    #             its bytes less its continuation bytes.
    local LC_ALL=C
    local s=${1//[$'\x80'-$'\xbf']/}
    REPLY=${#s}
}

pytext_ljust() {
    #  RETURN: 0, REPLY = '$1' filled with blanks to '$2' CHARACTERS, as
    #             Python's '%-Ns' fills -- not to bytes, as printf does.
    local text=$1 width=$2 pad
    pytext_char_n "$text"
    printf -v pad '%*s' $(( width > REPLY ? width - REPLY : 0 )) ''
    REPLY=$text$pad
}

pytext_sorted() {
    #  RETURN: 0, REPLY_LIST = the elements of the array named '$1', sorted
    #             as Python sorts str: by code point (= byte order of
    #             UTF-8), stable. An insertion sort: the lists are short.
    local LC_ALL=C
    local -n _pytext_list=$1
    local i j item
    REPLY_LIST=("${_pytext_list[@]}")
    for (( i = 1; i < ${#REPLY_LIST[@]}; ++i )); do
        item=${REPLY_LIST[i]}
        for (( j = i - 1; j >= 0; --j )); do
            [[ ${REPLY_LIST[j]} > $item ]] || break
            REPLY_LIST[j+1]=${REPLY_LIST[j]}
        done
        REPLY_LIST[j+1]=$item
    done
}

pytext_sorted_words() {
    #  RETURN: 0, REPLY_LIST = the words '$@', sorted as 'pytext_sorted'
    #             sorts.
    local _pytext_words=("$@")
    pytext_sorted _pytext_words
}
