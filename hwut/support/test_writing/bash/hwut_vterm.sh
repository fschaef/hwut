# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
#          'python/hwut_vterm.py' (its README: '../python/README-
#          hwut_vterm.txt'): libvterm's screen, cells and events, and an
#          application run on a pseudo-terminal it cannot tell from a
#          person's.
#
#     vterm_screen_new s 24 80 || { echo "NOT PROBED: $VTERM_ERROR"; exit; }
#     vterm_feed s $'\e[1mbold\e[0m plain'
#     vterm_line s 0                      # REPLY='bold plain'
#     vterm_cell s 0 0 cell               # cell[text]=b cell[bold_f]=1 ...
#     vterm_close s
#
#     vterm_terminal_new t 10 44          # settle_s: 0.1
#     vterm_region t read 8               # name row [row_n column column_n]
#     vterm_on_change t said              # said <name> <line> ...
#     vterm_run t -- python3 app.py       # options before '--': cwd= start_s=
#     vterm_press t up shift              # key, modifiers; react_s=<s>
#     vterm_send t q; vterm_wait t        # REPLY = the exit status
#     vterm_close t
#
# BASH CANNOT CALL A C LIBRARY, open a pseudo-terminal or read one under a
# timeout. So the C port does it: 'hwut_vterm_server' -- '../c/hwut_vterm.c'
# behind a line protocol, built by the 'Makefile' here ON FIRST USE -- runs
# as this shell's coprocess; one server serves every screen and terminal of
# the process, and ends when the last one is closed. A callback ('on_event',
# 'on_change') is a bash function, called while the command that caused it
# runs, in the order the C module calls its own.
#
# THE OBJECT is an associative array named by the caller. A function that
# fails returns 1: VTERM_ERROR_KIND is Python's exception name --
# 'LibraryMissing', 'IndexError', 'KeyError', 'TimeoutError',
# 'RuntimeError' -- VTERM_ERROR its text. A result stands in REPLY or
# REPLY_LIST; a bool is the status.
#______________________________________________________________________________
[[ -n ${_HWUT_VTERM_SH:-} ]] && return 0
_HWUT_VTERM_SH=1

VTERM_LIBRARY_VARIABLE=HWUT_LIBVTERM
VTERM_ATTRIBUTE_NAMES=(bold italic underline blink reverse conceal strike)
declare -gA VTERM_ATTRIBUTE_SGR=([bold]=1 [italic]=3 [underline]=4 [blink]=5 [reverse]=7 [conceal]=8 [strike]=9)
VTERM_ERROR_KIND=""
VTERM_ERROR=""

_VTERM_DIRECTORY=${BASH_SOURCE[0]%/*}
_VTERM_SERVER_PROGRAM=$_VTERM_DIRECTORY/hwut_vterm_server
_vterm_server_in=""                     # the server's stdin, written here
_vterm_server_out=""                    # its stdout, read here
_vterm_server_pid=""
_vterm_next_id=1
declare -gA _vterm_object=()            # id -> object name, of every open one

# ------------------------------------------------------------ the transport
_vterm_encode() {
    #  RETURN: 0, REPLY = '$1' %-encoded for the server: every blank, '%',
    #             '\', control byte and byte beyond ASCII as '%XX'; '%' for
    #             the empty text.
    local LC_ALL=C
    local s=$1 head c code
    if [[ -z $s ]]; then REPLY=%; return 0; fi
    s=${s//%/%25}; s=${s//\\/%5C}; s=${s// /%20}
    while [[ $s == *[$'\x01'-$'\x1f'$'\x7f'-$'\xff']* ]]; do
        head=${s%%[$'\x01'-$'\x1f'$'\x7f'-$'\xff']*}
        c=${s:${#head}:1}
        printf -v code '%%%02X' "'$c"
        s=${s//"$c"/$code}
    done
    REPLY=$s
}

_vterm_decode() {
    #  RETURN: 0, REPLY = the text the %-encoded field '$1' carries.
    if [[ $1 == % ]]; then REPLY=""; return 0; fi
    printf -v REPLY '%b' "${1//%/\\x}"
}

_vterm_start() {
    #  RETURN: 0, the server runs as this shell's coprocess -- built first
    #             where it is missing or older than its sources;
    #          1, it cannot be built (VTERM_ERROR: what make said).
    [[ -n $_vterm_server_pid ]] && return 0
    local source stale_f=0
    [[ -x $_VTERM_SERVER_PROGRAM ]] || stale_f=1
    for source in "$_VTERM_DIRECTORY/hwut_vterm_server.c" "$_VTERM_DIRECTORY/../c/hwut_vterm.c" \
                  "$_VTERM_DIRECTORY/../c/hwut_vterm.h"; do
        [[ $source -nt $_VTERM_SERVER_PROGRAM ]] && stale_f=1
    done
    if (( stale_f )); then
        local said
        if ! said=$(make -s -C "$_VTERM_DIRECTORY" hwut_vterm_server 2>&1 </dev/null); then
            VTERM_ERROR_KIND=RuntimeError
            VTERM_ERROR="'hwut_vterm_server' cannot be built in '$_VTERM_DIRECTORY':"$'\n'"$said"
            return 1
        fi
    fi
    coproc _VTERM_SERVER { exec "$_VTERM_SERVER_PROGRAM"; }
    #  THE DESCRIPTORS ARE KEPT: bash forgets the coprocess's array when
    #  it ends.
    _vterm_server_out=${_VTERM_SERVER[0]} _vterm_server_in=${_VTERM_SERVER[1]}
    _vterm_server_pid=$_VTERM_SERVER_PID
}

_vterm_stop() {
    #  RETURN: 0; the server got the end of its input and ended; the next
    #          object starts a new one.
    [[ -z $_vterm_server_pid ]] && return 0
    exec {_vterm_server_in}>&- {_vterm_server_out}<&-
    wait "$_vterm_server_pid" 2>/dev/null
    _vterm_server_pid="" _vterm_server_in="" _vterm_server_out=""
}

_vterm_call() {
    #  RETURN: 0, VTERM_REPLY = the fields of the server's 'ok' to the
    #             command line '$1' (fields encoded);
    #          1, it said 'err' (VTERM_ERROR_KIND, VTERM_ERROR), or ended.
    #  What the server reports while the command runs -- an event, a
    #  changed region -- is handed to the object's callbacks first.
    local -a field
    _vterm_start || return 1
    printf '%s\n' "$1" >&"$_vterm_server_in"
    while IFS=' ' read -r -a field -u "$_vterm_server_out"; do
        case ${field[0]} in
            ok)     VTERM_REPLY=("${field[@]:1}"); return 0 ;;
            err)    VTERM_ERROR_KIND=${field[1]}
                    _vterm_decode "${field[2]-%}"; VTERM_ERROR=$REPLY
                    return 1 ;;
            event)  _vterm_tell event "${field[@]:1}" ;;
            change) _vterm_tell change "${field[@]:1}" ;;
        esac
    done
    VTERM_ERROR_KIND=RuntimeError VTERM_ERROR="the vterm server ended"
    return 1
}

_vterm_tell() {
    #  RETURN: 0; the report '$1' ('event' or 'change') of object number
    #          '$2' reached every callback of its kind: an event's function
    #          is called with the event's text, a change's with the region's
    #          name and its lines.
    local kind=$1 id=$2 item f; shift 2
    local -a decoded=()
    for item; do _vterm_decode "$item"; decoded+=("$REPLY"); done
    local -n _vt_self=${_vterm_object[$id]}
    for f in ${_vt_self[${kind}_f]}; do "$f" "${decoded[@]}"; done
}

_vterm_library_field() {
    #  RETURN: 0, REPLY = HWUT_LIBVTERM's value now, encoded; '%' unset.
    if [[ -n ${HWUT_LIBVTERM+x} ]]; then _vterm_encode "$HWUT_LIBVTERM"; else REPLY=%; fi
}

# ------------------------------------------------------------- the library
vterm_detection_text() {
    #  RETURN: 0, REPLY = 'libvterm found: <name>' where the library loads;
    #             else the text of 'LibraryMissing' -- what is wrong and
    #             how to install it.
    _vterm_call detect || { REPLY=$VTERM_ERROR; return 1; }
    _vterm_decode "${VTERM_REPLY[0]}"
}

vterm_reset_library() {
    #  RETURN: 0; the library is looked for again at the next screen, under
    #          the name HWUT_LIBVTERM gives then -- as
    #          'hwut_vterm._library = None'.
    [[ -z $_vterm_server_pid ]] && return 0
    _vterm_call reset_library
}

# -------------------------------------------------------------- the screen
vterm_screen_new() {
    #  RETURN: 0, the global associative array named '$1' is a screen of
    #             '$2' rows (24) and '$3' columns (80), blank;
    #          1, the library is not found ('LibraryMissing', with the hint
    #             how to install it).
    local id=$_vterm_next_id
    _vterm_library_field
    _vterm_call "screen_new $id ${2:-24} ${3:-80} $REPLY" || return 1
    (( ++_vterm_next_id ))
    declare -gA "$1"
    local -n _vt_self=$1
    _vt_self=([id]=$id [row_n]=${2:-24} [column_n]=${3:-80} [event_f]="" [change_f]="")
    _vterm_object[$id]=$1
}

vterm_close() {
    #  RETURN: 0; the screen or terminal '$1' is closed -- an application
    #          still running in it killed. The last one closed ends the
    #          server.
    local -n _vt_self=$1
    [[ -z ${_vt_self[id]-} || -z ${_vterm_object[${_vt_self[id]}]+x} ]] && return 0
    _vterm_call "free ${_vt_self[id]}"
    unset "_vterm_object[${_vt_self[id]}]"
    (( ${#_vterm_object[@]} )) || _vterm_stop
}

vterm_feed() {
    #  RETURN: 0, REPLY = the number of bytes of '$2' the screen '$1' took
    #             -- a terminal's raw events fired before, its answer went
    #             to the application where one runs.
    local -n _vt_self=$1
    _vterm_encode "$2"
    _vterm_call "feed ${_vt_self[id]} $REPLY" || return 1
    REPLY=${VTERM_REPLY[0]}
}

vterm_cursor() {
    #  RETURN: 0, REPLY_LIST = (row column) of the cursor of screen '$1',
    #             counted from 0; REPLY = '(row, column)', as Python prints
    #             the tuple.
    local -n _vt_self=$1
    _vterm_call "cursor ${_vt_self[id]}" || return 1
    REPLY_LIST=("${VTERM_REPLY[@]}")
    REPLY="(${VTERM_REPLY[0]}, ${VTERM_REPLY[1]})"
}

vterm_cell() {
    #  RETURN: 0, the associative array named '$4' (default 'VTERM_CELL') is
    #             the cell at row '$2', column '$3' of screen '$1': 'text'
    #             ('' for an unwritten cell and the right half of a wide
    #             one), 'width', 'bold_f' 'italic_f' 'underline_f' 'blink_f'
    #             'reverse_f' 'conceal_f' 'strike_f' (0 or 1), 'foreground'
    #             and 'background' ('r g b', '' for the default);
    #          1, the place is not on the screen ('IndexError').
    local -n _vt_self=$1
    local cell_name=${4:-VTERM_CELL}
    _vterm_call "cell ${_vt_self[id]} $2 $3" || return 1
    declare -gA "$cell_name"
    local -n _vt_cell=$cell_name
    local -a f=("${VTERM_REPLY[@]}")
    _vterm_decode "${f[0]}"
    _vt_cell=([text]=$REPLY [width]=${f[1]} [bold_f]=${f[2]} [italic_f]=${f[3]} [underline_f]=${f[4]}
              [blink_f]=${f[5]} [reverse_f]=${f[6]} [conceal_f]=${f[7]} [strike_f]=${f[8]}
              [foreground]="" [background]="")
    (( f[9] ))  && _vt_cell[foreground]="${f[10]} ${f[11]} ${f[12]}"
    (( f[13] )) && _vt_cell[background]="${f[14]} ${f[15]} ${f[16]}"
    return 0
}

vterm_cell_attribute_text() {
    #  RETURN: 0, REPLY = the attributes set in the cell '$1', by name and in
    #             one fixed order, separated by blanks -- 'bold reverse';
    #             '' where none is set.
    local -n _vt_cell=$1
    local name out=""
    for name in "${VTERM_ATTRIBUTE_NAMES[@]}"; do
        (( _vt_cell[${name}_f] )) && out+="${out:+ }$name"
    done
    REPLY=$out
}

vterm_cell_colour_text() {
    #  RETURN: 0, REPLY = the colour 'r g b' of cell '$1's '$2'
    #             ('foreground', 'background') as Python prints the tuple
    #             -- '(255, 0, 0)' -- or 'None' for the default.
    local -n _vt_cell=$1
    local -a rgb=(${_vt_cell[$2]})
    if (( ${#rgb[@]} )); then REPLY="(${rgb[0]}, ${rgb[1]}, ${rgb[2]})"; else REPLY=None; fi
}

vterm_line() {
    #  RETURN: 0, REPLY = row '$2' of screen '$1', blanks at its end dropped.
    vterm_line_list "$1" || return 1
    REPLY=${REPLY_LIST[$2]}
}

vterm_line_list() {
    #  RETURN: 0, REPLY_LIST = every row of screen '$1', blanks at each
    #             end dropped.
    local -n _vt_self=$1
    local item
    _vterm_call "lines ${_vt_self[id]}" || return 1
    REPLY_LIST=()
    for item in "${VTERM_REPLY[@]}"; do _vterm_decode "$item"; REPLY_LIST+=("$REPLY"); done
}

# ------------------------------------------------------------ the terminal
vterm_terminal_new() {
    #  RETURN: 0, the global associative array named '$1' is a terminal of
    #             '$2' rows (24), '$3' columns (80), nothing running in it;
    #             '$4' (0.1) is how long the application must write nothing
    #             before its screen is taken as drawn;
    #          1, the library is not found ('LibraryMissing').
    #  Every 'vterm_screen'-function applies to a terminal too.
    local id=$_vterm_next_id
    _vterm_library_field
    _vterm_call "terminal_new $id ${2:-24} ${3:-80} ${4:-0.1} $REPLY" || return 1
    (( ++_vterm_next_id ))
    declare -gA "$1"
    local -n _vt_self=$1
    _vt_self=([id]=$id [row_n]=${2:-24} [column_n]=${3:-80} [settle_s]=${4:-0.1} [event_f]="" [change_f]="")
    _vterm_object[$id]=$1
}

vterm_on_event() {
    #  RETURN: 0; the function '$2' is called with every raw event of
    #          terminal '$1' from now on: '$2 <text> ' -- 'cursor    (0, 2)',
    #          'damage    rows 0..1  columns 0..2', 'property  <name> =
    #          <value>', 'bell'.
    local -n _vt_self=$1
    _vt_self[event_f]+=" $2"
    _vterm_call "on_event ${_vt_self[id]}"
}

vterm_on_change() {
    #  RETURN: 0; the function '$2' is called for every region of terminal
    #          '$1' whose text changed, once the screen is quiet: '$2 <name>
    #          <line> ...'.
    local -n _vt_self=$1
    _vt_self[change_f]+=" $2"
    _vterm_call "on_change ${_vt_self[id]}"
}

vterm_region() {
    #  RETURN: 0; the rectangle '$2' of terminal '$1' is observed from now
    #          on: '$4' rows (1) from row '$3', '$6' columns (to the right
    #          edge where none or negative) from column '$5' (0). A NEGATIVE
    #          row counts from the bottom: -1 is the last row. What stands
    #          there now is known, not news.
    local -n _vt_self=$1
    _vterm_encode "$2"
    _vterm_call "region ${_vt_self[id]} $REPLY $3 ${4:-1} ${5:-0} ${6:--1}"
}

vterm_region_text() {
    #  RETURN: 0, REPLY_LIST = the rows of region '$2' of terminal '$1' as
    #             they stand now, blanks at each end dropped;
    #          1, no such region was declared ('KeyError').
    local -n _vt_self=$1
    local item
    _vterm_encode "$2"
    _vterm_call "region_text ${_vt_self[id]} $REPLY" || return 1
    REPLY_LIST=()
    for item in "${VTERM_REPLY[@]}"; do _vterm_decode "$item"; REPLY_LIST+=("$REPLY"); done
}

vterm_report() {
    #  RETURN: 0, REPLY = the number of regions of terminal '$1' whose text
    #             differs from what was last told -- each told to every
    #             'on_change' function, in the order of declaration.
    local -n _vt_self=$1
    _vterm_call "report ${_vt_self[id]}" || return 1
    REPLY=${VTERM_REPLY[0]}
}

vterm_answer() {
    #  RETURN: 0, REPLY = the bytes terminal '$1' said since the last call
    #             and no application took -- a key's sequence, an answer.
    local -n _vt_self=$1
    _vterm_call "answer ${_vt_self[id]}" || return 1
    _vterm_decode "${VTERM_REPLY[0]}"
}

_vterm_react_option() {
    #  RETURN: 0, REPLY = the seconds the word 'react_s=<s>' among '$2...'
    #             names, '$1' where none does; REPLY_LIST = the other words.
    local word
    REPLY=$1 REPLY_LIST=()
    shift
    for word; do
        if [[ $word == react_s=* ]]; then REPLY=${word#react_s=}; else REPLY_LIST+=("$word"); fi
    done
}

vterm_send() {
    #  RETURN: 0, the application in terminal '$1' still runs after the
    #             text '$2' (UTF-8) was typed character by character, as a
    #             keyboard sends it, and the screen read until quiet
    #             ('react_s=<s>': 1.0 s to begin answering);
    #          1, it does not.
    local -n _vt_self=$1
    local text=$2 react
    _vterm_react_option 1.0 "${@:3}"; react=$REPLY
    _vterm_encode "$text"
    _vterm_call "send ${_vt_self[id]} $REPLY $react" || return 1
    (( VTERM_REPLY[0] ))
}

vterm_press() {
    #  RETURN: 0, the application in terminal '$1' still runs after the key
    #             '$2' was pressed with the modifiers '$3...' ('shift',
    #             'alt', 'ctrl'; 'react_s=<s>' among them: 1.0 s);
    #          1, it does not, or a key or modifier has no name here
    #             ('KeyError').
    #  The key is 'enter', 'up', 'f5', ... or one character.
    local -n _vt_self=$1
    local key=$2 react modifiers
    _vterm_react_option 1.0 "${@:3}"; react=$REPLY
    _vterm_encode "${REPLY_LIST[*]}"; modifiers=$REPLY
    _vterm_encode "$key"
    _vterm_call "press ${_vt_self[id]} $REPLY $modifiers $react" || return 1
    (( VTERM_REPLY[0] ))
}

vterm_run() {
    #  RETURN: 0, the application '<argv>' still runs once its first screen
    #             stands;
    #          1, it does not -- or one already ran here ('RuntimeError').
    #  Words before '--' are options: 'cwd=<dir>', 'start_s=<s>' (10.0).
    #  The application is started on a pseudo-terminal of terminal '$1's
    #  size, with this shell's exported environment: its three streams are
    #  that terminal, it is the controlling one, TERM is 'xterm-256color',
    #  and LINES and COLUMNS are taken OUT -- they would overrule the size.
    local -n _vt_self=$1; shift
    local cwd=% start_s=10.0 word name line=""
    while (( $# )) && [[ $1 == *=* || $1 == -- ]]; do
        word=$1; shift
        case $word in
            --)        break ;;
            cwd=*)     _vterm_encode "${word#cwd=}"; cwd=$REPLY ;;
            start_s=*) start_s=${word#start_s=} ;;
            *)         set -- "$word" "$@"; break ;;
        esac
    done
    local -a environment=()
    for name in $(compgen -e); do
        [[ $name == LINES || $name == COLUMNS ]] && continue
        _vterm_encode "$name=${!name}"; environment+=("$REPLY")
    done
    environment+=("TERM=xterm-256color")
    for word; do _vterm_encode "$word"; line+=" $REPLY"; done
    _vterm_call "run ${_vt_self[id]} $cwd $start_s ${#environment[@]} ${environment[*]}$line" || return 1
    (( VTERM_REPLY[0] ))
}

vterm_pump() {
    #  RETURN: 0, the application in terminal '$1' still runs; 1, it does
    #             not. READ UNTIL QUIET: up to '$2' (1.0) s for it to write
    #             at all, then on until it wrote nothing for 'settle_s'; the
    #             changed regions are reported.
    local -n _vt_self=$1
    _vterm_call "pump ${_vt_self[id]} ${2:-1.0}" || return 1
    (( VTERM_REPLY[0] ))
}

vterm_expect() {
    #  RETURN: 0, REPLY_LIST = (row column) where the text '$2' stands on
    #             the screen of terminal '$1', once it does;
    #          1, it did not within '$3' (10.0) s ('TimeoutError', carrying
    #             the screen).
    local -n _vt_self=$1
    _vterm_encode "$2"
    _vterm_call "expect ${_vt_self[id]} $REPLY ${3:-10.0}" || return 1
    REPLY_LIST=("${VTERM_REPLY[@]}")
}

vterm_wait() {
    #  RETURN: 0, REPLY = the application's exit status (negative: the
    #             signal that ended it) once it ended and its last words are
    #             on the screen -- 'None' where none was run;
    #          1, it still ran after '$2' (10.0) s and was killed
    #             ('TimeoutError').
    local -n _vt_self=$1
    _vterm_call "wait ${_vt_self[id]} ${2:-10.0}" || return 1
    REPLY=${VTERM_REPLY[0]}
}
