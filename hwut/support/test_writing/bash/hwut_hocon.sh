# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
#          ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (its README:
#          '../python/README-hwut_hocon.txt'): every key, every value and
#          every block carries its file-relative position.
#
#     hocon_source_lines src $'a = 1\nb = "x"'      # line offset, column offset
#     hocon_parse doc src f.hocon
#     hocon_get doc "${doc[root]}" a && echo "${doc_value[REPLY]}"     # 1
#     for (( i = 0; i < ${#doc_fault_message[@]}; ++i )); do
#         hocon_fault_text doc $i; echo "FAULT $REPLY"
#     done
#
# THE SOURCE LINES are three arrays: '<src>_text', '<src>_line' and
# '<src>_column_offset' (what was removed before the text) -- Python's
# SourceLine.
#
# THE TREE is the associative array '<doc>' ('root': the document's node)
# and arrays indexed by node: '<doc>_kind' -- 'object', 'list', 'str',
# 'int', 'float', 'bool', 'NoneType' (Python's type names) --
# '<doc>_value' (a scalar's: the text, the decimal, the float as written
# without '_', 'True'/'False'), '<doc>_position' ('line:column'),
# '<doc>_children' (an object's entries, a list's items: node numbers),
# and for an entry's value '<doc>_key', '<doc>_key_position'. The faults:
# '<doc>_fault_kind' ('SYNTAX', 'REFUSED'), '_fault_file',
# '_fault_position', '_fault_message'.
#
# The parser accumulates faults and recovers at the next line; it never
# fails. A bound -- 'bound_s=0.5' -- ends a parse that runs past it: status
# 2, the tree as far as read (Python's test raises from SIGALRM; bash has no
# way to leave a function from a trap, so the parse's loops look at the
# clock). The scan works on bytes (LC_ALL=C), a column counts characters.
#______________________________________________________________________________
[[ -n ${_HWUT_HOCON_SH:-} ]] && return 0
_HWUT_HOCON_SH=1
source "${BASH_SOURCE[0]%/*}/hwut_pytext.sh"

#  A TOKEN -- a key, or a bare value -- runs to the first character that
#  binds, opens, closes or separates; a blank ends it too (R-49).
_HOCON_TOKEN_RE='^[^][:space:]{}=,:"#[]*'
_HOCON_DECIMAL_RE='^[-+]?([0-9](_?[0-9])*(\.([0-9](_?[0-9])*)?)?|\.[0-9](_?[0-9])*)([eE][-+]?[0-9](_?[0-9])*)?$'
_HOCON_ROMAN_RE='^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
_HOCON_QUOTED_PLAIN_RE='^([^"\\]*)"'
_HOCON_TRIPLE='"""'
declare -gA _HOCON_ROMAN_VALUE=([I]=1 [V]=5 [X]=10 [L]=50 [C]=100 [D]=500 [M]=1000)
declare -gA _HOCON_RADIX=([0x]=16 [0X]=16 [0b]=2 [0B]=2 [0o]=8 [0O]=8)
declare -gA _HOCON_RADIX_DIGITS=([16]='0-9a-fA-F' [2]='01' [8]='0-7')

hocon_source_lines() {
    #  RETURN: 0; the source lines '$1' hold the text '$2' split at its
    #          newlines, numbered from 1 + '$3' (default 0), each with the
    #          column offset '$4' (default 0).
    declare -ga "$1_text" "$1_line" "$1_column_offset"
    local -n _hs_text=$1_text _hs_line=$1_line _hs_offset=$1_column_offset
    local i
    mapfile -t _hs_text <<< "$2"
    _hs_line=() _hs_offset=()
    for (( i = 0; i < ${#_hs_text[@]}; ++i )); do
        _hs_line[i]=$(( i + 1 + ${3:-0} )); _hs_offset[i]=${4:-0}
    done
}

hocon_parse() {
    #  RETURN: 0, the tree '$1' (see the head) is the document the source
    #             lines '$2' hold -- every entry of the outermost level,
    #             possibly none -- and its faults name the file '$3';
    #          2, the option 'bound_s=<seconds>' was given and the parse ran
    #             past it: the tree stands as far as it was read.
    local doc=$1 src=$2 file=$3 option bound_s=""
    for option in "${@:4}"; do [[ $option == bound_s=* ]] && bound_s=${option#bound_s=}; done
    [[ ${LC_ALL-} == C ]] || local LC_ALL=C
    declare -gA "$doc"
    declare -ga "${doc}_kind" "${doc}_value" "${doc}_position" "${doc}_children" \
                "${doc}_key" "${doc}_key_position" \
                "${doc}_fault_kind" "${doc}_fault_file" "${doc}_fault_position" "${doc}_fault_message"
    local -n _hd=$doc _hk=${doc}_kind _hv=${doc}_value _hp=${doc}_position _hc=${doc}_children
    local -n _hkey=${doc}_key _hkp=${doc}_key_position
    local -n _hfk=${doc}_fault_kind _hff=${doc}_fault_file _hfp=${doc}_fault_position _hfm=${doc}_fault_message
    local -n _hlt=${src}_text _hll=${src}_line _hlo=${src}_column_offset
    _hd=() _hk=() _hv=() _hp=() _hc=() _hkey=() _hkp=() _hfk=() _hff=() _hfm=() _hfp=()
    #  THE CURSOR: line, column (a byte index into the line), the line's text.
    local _hl_n=${#_hlt[@]} _hi_line=-1 _hi_col=0 _ht="" _hn=0 _hfile=$file _hwide_f=0
    local -A _hkeys=()                                  # object|key -> 1
    local _hdeadline=0 _hhang_f=0 _hocon_kind=""
    if [[ -n $bound_s ]]; then
        local micro
        printf -v micro '%.0f' "${bound_s}e6" 2>/dev/null || micro=$(( ${bound_s%.*} * 1000000 ))
        _hdeadline=$(( ${EPOCHREALTIME/./} + micro ))
    fi
    _hocon_skip_line                                    # onto the first line
    _hocon_body ""
    _hd[root]=$REPLY
    (( _hhang_f )) && return 2
    return 0
}

hocon_fault_text() {
    #  RETURN: 0, REPLY = fault '$2' of the tree '$1' as Python's
    #             'str(ParseFault)' writes it: 'file:line:column: KIND:
    #             message'.
    local -n _hfk=$1_fault_kind _hff=$1_fault_file _hfp=$1_fault_position _hfm=$1_fault_message
    REPLY="${_hff[$2]}:${_hfp[$2]}: ${_hfk[$2]}: ${_hfm[$2]}"
}

hocon_get() {
    #  RETURN: 0, REPLY = the node of the entry named '$3' in the object
    #             node '$2' of the tree '$1';
    #          1, no such entry.
    local -n _hc=$1_children _hkey=$1_key
    local child
    for child in ${_hc[$2]}; do
        [[ ${_hkey[child]} == "$3" ]] && { REPLY=$child; return 0; }
    done
    return 1
}

hocon_keys() {
    #  RETURN: 0, REPLY_LIST = the keys of the object node '$2' of the tree
    #             '$1', in written order.
    local -n _hc=$1_children _hkey=$1_key
    local child
    REPLY_LIST=()
    for child in ${_hc[$2]}; do REPLY_LIST+=("${_hkey[child]}"); done
}

hocon_value_repr() {
    #  RETURN: 0, REPLY = the value of the scalar node '$2' of the tree '$1'
    #             as Python's '%r' writes it: a str quoted, a float in its
    #             shortest form, True, False, None.
    local -n _hk=$1_kind _hv=$1_value
    case ${_hk[$2]} in
        str)      pytext_str_repr "${_hv[$2]}" ;;
        float)    pytext_float_repr "${_hv[$2]}" ;;
        NoneType) REPLY=None ;;
        *)        REPLY=${_hv[$2]} ;;
    esac
}

hocon_cleandoc() {
    #  RETURN: 0, REPLY = the text '$1' laid out as Python's
    #             'inspect.cleandoc' lays out a docstring: tabs expanded,
    #             the indentation common to the lines after the first
    #             removed, the first line's removed, blank lines at the
    #             beginning and the end dropped.
    local LC_ALL=C
    local -a line_list
    local line i content margin=-1 text=$1
    [[ $text == *$'\t'* ]] && { _hocon_expandtabs "$text"; text=$REPLY; }
    mapfile -t line_list <<< "$text"
    for (( i = 1; i < ${#line_list[@]}; ++i )); do
        line=${line_list[i]}
        content=${line#"${line%%[![:space:]]*}"}
        if [[ -n $content ]]; then
            local indent=$(( ${#line} - ${#content} ))
            (( margin < 0 || indent < margin )) && margin=$indent
        fi
    done
    (( ${#line_list[@]} )) && line_list[0]=${line_list[0]#"${line_list[0]%%[![:space:]]*}"}
    if (( margin >= 0 )); then
        for (( i = 1; i < ${#line_list[@]}; ++i )); do line_list[i]=${line_list[i]:margin}; done
    fi
    while (( ${#line_list[@]} )) && [[ -z ${line_list[-1]} ]]; do unset 'line_list[-1]'; done
    while (( ${#line_list[@]} )) && [[ -z ${line_list[0]} ]]; do line_list=("${line_list[@]:1}"); done
    printf -v REPLY '%s\n' "${line_list[@]}"
    REPLY=${REPLY%$'\n'}
}

_hocon_expandtabs() {
    #  RETURN: 0, REPLY = '$1' with every tab replaced by blanks up to the
    #             next column that is a multiple of 8; a line end restarts
    #             the count -- Python's 'str.expandtabs()'.
    local text=$1 out="" c i column=0
    for (( i = 0; i < ${#text}; ++i )); do
        c=${text:i:1}
        case $c in
            $'\t')       local n=$(( 8 - column % 8 )); printf -v c '%*s' $n ''; out+=$c; (( column += n )) ;;
            $'\n'|$'\r') out+=$c; column=0 ;;
            *)           out+=$c; (( ++column )) ;;
        esac
    done
    REPLY=$out
}

# ---------------------------------------------------------------- the cursor
_hocon_skip_line() {
    #  RETURN: 0; the cursor stands at the beginning of the next line;
    #          '_hwide_f' says whether that line holds a byte beyond ASCII.
    (( ++_hi_line )); _hi_col=0
    _ht=${_hlt[_hi_line]-}
    [[ $_ht == *[$'\x80'-$'\xff']* ]] && _hwide_f=1 || _hwide_f=0
}

_hocon_position() {
    #  RETURN: 0, REPLY = 'line:column', file-relative, of the character at
    #             the cursor -- the column in CHARACTERS (UTF-8).
    if (( ! _hwide_f && _hi_line < _hl_n )); then
        REPLY=${_hll[_hi_line]}:$(( _hlo[_hi_line] + _hi_col + 1 )); return
    fi
    local text
    if (( _hi_line >= _hl_n )); then
        if (( _hl_n == 0 )); then REPLY=1:1; return; fi
        text=${_hlt[_hl_n-1]}; text=${text//[$'\x80'-$'\xbf']/}
        REPLY=${_hll[_hl_n-1]}:$(( _hlo[_hl_n-1] + ${#text} + 1 ))
        return
    fi
    text=${_ht:0:_hi_col}; text=${text//[$'\x80'-$'\xbf']/}
    REPLY=${_hll[_hi_line]}:$(( _hlo[_hi_line] + ${#text} + 1 ))
}

_hocon_fault() {
    #  RETURN: 0; the fault of kind '$1' at the position '$2' saying '$3' is
    #          recorded.
    _hfk+=("$1"); _hff+=("$_hfile"); _hfp+=("$2"); _hfm+=("$3")
}

_hocon_node() {
    #  RETURN: 0, REPLY = a new node of kind '$1', value '$2', at the
    #             position '$3'.
    REPLY=$_hn
    _hk[_hn]=$1; _hv[_hn]=$2; _hp[_hn]=$3; _hc[_hn]=""
    (( ++_hn ))
}

_hocon_hang() {
    #  RETURN: 0; the parse ran past its bound: it is marked hung and the
    #          cursor put at the end -- every loop then ends.
    _hhang_f=1; _hi_line=$_hl_n; _ht=""; _hwide_f=0
}

_hocon_skip_space() {
    #  RETURN: 0; blanks and a comment on the current line are skipped.
    #  The most called function of the parser: the common case -- nothing
    #  to skip -- is decided on one character.
    case ${_ht:_hi_col:1} in
        [$' \t'])
            local rest=${_ht:_hi_col}
            local blank=${rest%%[!$' \t']*}
            (( _hi_col += ${#blank} ))
            [[ ${_ht:_hi_col:1} == '#' || ${_ht:_hi_col:2} == '//' ]] && _hocon_skip_line ;;
        '#')  _hocon_skip_line ;;
        /)    [[ ${_ht:_hi_col:2} == '//' ]] && _hocon_skip_line ;;
    esac
    return 0
}

_hocon_skip_blank() {
    #  RETURN: 0; blanks, newlines, commas and comments are skipped; a line
    #          whose remainder is blank, or a comment, is left in one step.
    local rest blank
    while (( _hi_line < _hl_n )); do
        case ${_ht:_hi_col:1} in
            "")         _hocon_skip_line; continue ;;
            '#')        _hocon_skip_line; continue ;;
            /)          [[ ${_ht:_hi_col:2} == '//' ]] || return 0
                        _hocon_skip_line; continue ;;
            [$' \t,'])  ;;
            *)          return 0 ;;
        esac
        rest=${_ht:_hi_col}
        blank=${rest%%[!$' \t,']*}
        if (( ${#blank} == ${#rest} )); then _hocon_skip_line; continue; fi
        (( _hi_col += ${#blank} ))
    done
}

# ---------------------------------------------------------------- the parse
_hocon_body() {
    #  RETURN: 0, REPLY = the object node of the entries up to the
    #             terminator '$1' ('}', or '' for the end of the text).
    local c id
    _hocon_position; _hocon_node object "" "$REPLY"; id=$REPLY
    while true; do
        _hocon_skip_blank
        if (( _hi_line >= _hl_n )); then
            if [[ -n $1 ]]; then
                _hocon_position
                _hocon_fault SYNTAX "$REPLY" "unterminated object: '$1' missing"
            fi
            break
        fi
        c=${_ht:_hi_col:1}
        if [[ -n $1 && $c == "$1" ]]; then (( ++_hi_col )); break; fi
        if [[ $c == "}" ]]; then
            _hocon_position; _hocon_fault SYNTAX "$REPLY" "unmatched '}'"
            (( ++_hi_col ))
        else
            _hocon_entry $id
        fi
        (( _hdeadline && ${EPOCHREALTIME/./} > _hdeadline )) && _hocon_hang
    done
    REPLY=$id
}

_hocon_entry() {
    #  RETURN: 0; one 'key = value' pair is parsed into the object node '$1';
    #          a fault recovers at the next line.
    local object=$1 key key_position c
    _hocon_position; key_position=$REPLY
    if ! _hocon_key; then _hocon_skip_line; return 0; fi
    key=$REPLY
    if [[ $key == include ]]; then
        _hocon_fault REFUSED "$key_position" "'include' does not exist here: a specification refers to nothing outside its file"
        _hocon_skip_line; return 0
    fi
    _hocon_skip_space
    c=${_ht:_hi_col:1}
    case $c in
        =|:) (( ++_hi_col )); _hocon_skip_space ;;
        "{") ;;                                         # a brace binds without a sign
        *)
            if [[ $c == + && ${_ht:_hi_col+1:1} == = ]]; then
                _hocon_position; _hocon_fault REFUSED "$REPLY" "'+=' does not exist here"
            else
                _hocon_position; _hocon_fault SYNTAX "$REPLY" "expected '=', ':' or '{' after key '$key'"
            fi
            _hocon_skip_line; return 0 ;;
    esac
    #  NO NODE: the value parser has recovered already; a second skip here
    #  would eat the NEXT line.
    _hocon_value 0 || return 0
    local node=$REPLY
    if [[ -n ${_hkeys[$object|$key]+x} ]]; then
        _hocon_fault SYNTAX "$key_position" "duplicate key '$key'; the first stands, this one is refused"
        return 0
    fi
    _hkeys[$object|$key]=1
    _hkey[node]=$key; _hkp[node]=$key_position
    _hc[object]+="${_hc[object]:+ }$node"
}

_hocon_key() {
    #  RETURN: 0, REPLY = the key at the cursor;
    #          1, no key stands here (fault recorded).
    if [[ ${_ht:_hi_col:1} == '"' ]]; then _hocon_quoted; return; fi
    [[ ${_ht:_hi_col} =~ $_HOCON_TOKEN_RE ]]
    if [[ -z ${BASH_REMATCH[0]} ]]; then
        local found=${_ht:_hi_col:1}
        [[ $found == [[:space:]] ]] && found=""
        _hocon_position
        _hocon_fault SYNTAX "$REPLY" "expected a key, found '$found'"
        return 1
    fi
    REPLY=${BASH_REMATCH[0]}
    (( _hi_col += ${#REPLY} ))
}

_hocon_value() {
    #  RETURN: 0, REPLY = the node of the value at the cursor;
    #          1, nothing usable stands here (fault recorded).
    #  '$1' 1 says an empty value is a fault rather than null: inside a
    #  list there is no key it could belong to.
    local position
    _hocon_skip_space
    _hocon_position; position=$REPLY
    case ${_ht:_hi_col:1} in
        "{") (( ++_hi_col )); _hocon_body "}" ;;
        "[") (( ++_hi_col )); _hocon_list "$position" ;;
        '"')
            if [[ ${_ht:_hi_col:3} == "$_HOCON_TRIPLE" ]]; then _hocon_triple_quoted || return 1
            else                                              _hocon_quoted        || return 1
            fi
            _hocon_node str "$REPLY" "$position" ;;
        '$')
            if [[ ${_ht:_hi_col+1:1} == "{" ]]; then
                _hocon_fault REFUSED "$position" "substitutions '\${...}' do not exist here: a specification refers to nothing outside its file"
                _hocon_skip_line
                return 1
            fi
            _hocon_bare "$position" "$1" ;;
        *)   _hocon_bare "$position" "$1" ;;
    esac
}

_hocon_list() {
    #  RETURN: 0, REPLY = the list node of the items up to ']', at the
    #             position '$1'.
    local id item_line item_col
    _hocon_node list "" "$1"; id=$REPLY
    while true; do
        _hocon_skip_blank
        if (( _hi_line >= _hl_n )); then
            _hocon_position; _hocon_fault SYNTAX "$REPLY" "unterminated list: ']' missing"
            break
        fi
        case ${_ht:_hi_col:1} in
            "]") (( ++_hi_col )); break ;;
            ",") (( ++_hi_col )) ;;
            "}")
                #  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was
                #  forgotten. Said once, and the brace left to its owner.
                _hocon_position; _hocon_fault SYNTAX "$REPLY" "unterminated list: ']' missing before '}'"
                break ;;
            *)
                item_line=$_hi_line item_col=$_hi_col
                if _hocon_value 1; then
                    _hc[id]+="${_hc[id]:+ }$REPLY"
                elif (( item_line == _hi_line && item_col == _hi_col )); then
                    #  NO VALUE READ AND NOTHING CONSUMED: step over the
                    #  character the value refused, or the loop never ends.
                    (( ++_hi_col ))
                fi ;;
        esac
        (( _hdeadline && ${EPOCHREALTIME/./} > _hdeadline )) && _hocon_hang
    done
    REPLY=$id
}

_hocon_triple_quoted() {
    #  RETURN: 0, REPLY = the text between three double quotes and the next
    #             three, over as many lines as it takes, AS WRITTEN, laid
    #             out by 'hocon_cleandoc';
    #          1, no closing three quotes stand before the text's end
    #             (fault recorded at the opening).
    local begin rest pieces=""
    _hocon_position; begin=$REPLY
    (( _hi_col += 3 ))
    while (( _hi_line < _hl_n )); do
        rest=${_ht:_hi_col}
        if [[ $rest == *"$_HOCON_TRIPLE"* ]]; then
            rest=${rest%%"$_HOCON_TRIPLE"*}
            (( _hi_col += ${#rest} + 3 ))
            hocon_cleandoc "$pieces$rest"
            return 0
        fi
        pieces+=$rest$'\n'
        _hocon_skip_line
    done
    _hocon_fault SYNTAX "$begin" "unterminated triple-quoted string: closing '\"\"\"' missing"
    return 1
}

_hocon_quoted() {
    #  RETURN: 0, REPLY = the string's content at the cursor, escapes
    #             resolved;
    #          1, the string is unterminated at its line's end (fault
    #             recorded).
    local begin i=$(( _hi_col + 1 )) out="" c escaped
    if [[ ${_ht:i} =~ $_HOCON_QUOTED_PLAIN_RE ]]; then
        _hi_col=$(( i + ${#BASH_REMATCH[0]} ))
        REPLY=${BASH_REMATCH[1]}
        return 0
    fi
    _hocon_position; begin=$REPLY
    while true; do
        if (( i >= ${#_ht} )); then
            _hocon_fault SYNTAX "$begin" "unterminated string"
            _hi_col=$i
            return 1
        fi
        c=${_ht:i:1}
        case $c in
            '"')  _hi_col=$(( i + 1 )); REPLY=$out; return 0 ;;
            \\)   escaped=${_ht:i+1:1}
                  case $escaped in
                      n) out+=$'\n' ;;
                      t) out+=$'\t' ;;
                      *) out+=$escaped ;;
                  esac
                  (( i += 2 )) ;;
            *)    out+=$c; (( ++i )) ;;
        esac
    done
}

_hocon_bare() {
    #  RETURN: 0, REPLY = the scalar node of the bare token at the cursor --
    #             a boolean, a number, a spelling of nothing -- at the
    #             position '$1';
    #          1, the token is none of those (fault recorded): a string
    #             value is written in double quotes.
    #  '$2' 1: an empty value is a fault (inside a list), not null.
    local position=$1 in_list_f=$2 raw after blank_end
    [[ ${_ht:_hi_col} =~ $_HOCON_TOKEN_RE ]]; raw=${BASH_REMATCH[0]}
    #  A SIGN STANDING APART from its digits: '- 0.12'. Where nothing but
    #  blanks lies between it and a number, and the two make ONE number,
    #  they are one ('- -0.12' makes none).
    if [[ $raw == [-+] ]]; then
        local rest=${_ht:_hi_col+1}
        local blank=${rest%%[!$' \t']*}
        blank_end=$(( _hi_col + 1 + ${#blank} ))
        [[ ${_ht:blank_end} =~ $_HOCON_TOKEN_RE ]]; after=${BASH_REMATCH[0]}
        if [[ -n $after ]] && _hocon_number "$after" && _hocon_number "$raw$after"; then
            _hi_col=$(( blank_end + ${#after} ))
            _hocon_node "${_hocon_kind}" "$REPLY" "$position"
            return 0
        fi
    fi
    if [[ $raw == '${'* ]]; then
        _hocon_position
        _hocon_fault REFUSED "$REPLY" "substitutions '\${...}' do not exist here"
        _hocon_skip_line
        return 1
    fi
    [[ $raw == *//* ]] && raw=${raw%%//*}
    (( _hi_col += ${#raw} ))
    if [[ -z $raw ]]; then
        if (( in_list_f )); then
            local found=${_ht:_hi_col:1}
            [[ $found == [[:space:]] ]] && found=""
            _hocon_fault SYNTAX "$position" "expected a value, found '$found'"
            return 1
        fi
        _hocon_node NoneType "" "$position"                 # an empty value is null
        return 0
    fi
    case $raw in
        null|nil|none|nihil) _hocon_node NoneType "" "$position"; return 0 ;;
        true|yes)            _hocon_node bool True "$position";   return 0 ;;
        false|no)            _hocon_node bool False "$position";  return 0 ;;
    esac
    if ! _hocon_number "$raw"; then
        _hocon_fault SYNTAX "$position" "a string is written in double quotes: \"$raw\""
        return 1
    fi
    _hocon_node "$_hocon_kind" "$REPLY" "$position"
}

_hocon_number() {
    #  RETURN: 0, REPLY = the number the text '$1' spells, in whatever radix
    #             it spells it, as a decimal ('int') or as written without
    #             '_' ('float') -- the kind in '_hocon_kind';
    #          1, the text spells no number.
    local raw=$1 body=$1 sign=""
    [[ $raw == [-+]* ]] && body=${raw:1}
    [[ $raw == -* ]] && sign=-
    local prefix=${body:0:2}
    _hocon_kind=int
    if [[ $prefix == 0[rR] ]]; then
        _hocon_roman "${body:2}" || return 1
        _hocon_signed "$sign" "$REPLY"
        return 0
    fi
    if [[ -n $prefix && -n ${_HOCON_RADIX[$prefix]+x} ]]; then
        local radix=${_HOCON_RADIX[$prefix]} digits=${body:2}
        #  '_' between digits only: none first, none last, never two.
        [[ -z $digits || $digits == _* || $digits == *_ || $digits == *__* ]] && return 1
        digits=${digits//_/}
        [[ -z $digits || $digits == *[!${_HOCON_RADIX_DIGITS[$radix]}]* ]] && return 1
        _hocon_radix_decimal "$radix" "$digits"
        _hocon_signed "$sign" "$REPLY"
        return 0
    fi
    [[ $raw =~ $_HOCON_DECIMAL_RE ]] || return 1
    local text=${raw//_/}
    if [[ $text == *[.eE]* ]]; then _hocon_kind=float; REPLY=$text; return 0; fi
    text=${text#[-+]}
    _hocon_signed "$sign" "$text"
}

_hocon_signed() {
    #  RETURN: 0, REPLY = the decimal digits '$2' as Python prints the int:
    #             leading zeros dropped, the sign '$1' ('-' or '') kept
    #             unless the value is 0.
    local digits=${2#"${2%%[!0]*}"}
    if [[ -z $digits ]]; then REPLY=0; else REPLY=$1$digits; fi
}

_hocon_radix_decimal() {
    #  RETURN: 0, REPLY = the decimal digits of the number the digits '$2'
    #             spell in radix '$1' -- of any length: beyond 60 bits the
    #             digits are carried in limbs of nine decimals, as Python's
    #             int has no bound.
    local radix=$1 digits=$2
    if (( ${#digits} * (radix == 16 ? 4 : radix == 8 ? 3 : 1) <= 60 )); then
        REPLY=$(( $radix#$digits )); return 0
    fi
    local -a limb=(0)                                   # little end first
    local i k d carry
    for (( i = 0; i < ${#digits}; ++i )); do
        d=$(( $radix#${digits:i:1} )) carry=$d
        for (( k = 0; k < ${#limb[@]}; ++k )); do
            carry=$(( limb[k] * radix + carry ))
            limb[k]=$(( carry % 1000000000 )) carry=$(( carry / 1000000000 ))
        done
        (( carry )) && limb+=("$carry")
    done
    REPLY=${limb[-1]}
    for (( k = ${#limb[@]} - 2; k >= 0; --k )); do printf -v d '%09d' "${limb[k]}"; REPLY+=$d; done
}

_hocon_roman() {
    #  RETURN: 0, REPLY = the number the roman numeral '$1' spells;
    #          1, it is no roman numeral -- 'IIII' and 'VX' among them: the
    #             form is the strict one.
    [[ -n $1 && $1 =~ $_HOCON_ROMAN_RE ]] || return 1
    local total=0 previous=0 value i
    for (( i = ${#1} - 1; i >= 0; --i )); do
        value=${_HOCON_ROMAN_VALUE[${1:i:1}]}
        if (( value < previous )); then (( total -= value )); else (( total += value )); fi
        (( value > previous )) && previous=$value
    done
    REPLY=$total
}
