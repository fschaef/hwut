#! /usr/bin/env bash
#______________________________________________________________________________
# THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
# 'fixture.py' of the Python demonstration, in bash.
#
#     fixture.sh open            a fresh 'TMP/shop.db', stocked as below, and
#                                an empty 'TMP/frame.log' ('on_entry', and
#                                'hwut.execute fixture open')
#     fixture.sh close           both removed ('on_exit')
#     fixture.sh check <when> <app> [<choice>]
#                                'when' is 'before' or 'after': whether the
#                                stock adds up around the test run '<app>
#                                <choice>', appended to 'TMP/frame.log'
#                                ('on_before_test', 'on_after_test')
#
# THE DATABASE is a directory of three tables, one text file each -- bash
# has no SQLite: 'opening' and 'stock' ('item qty' per line), 'journal'
# ('item delta source' per line); a writer holds 'lock' ('flock'), one at a
# time, as SQLite's one writer. The stock ADDS UP where every item's
# quantity is its opening quantity plus every movement of the journal.
#______________________________________________________________________________
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DB_PATH=$HERE/TMP/shop.db
LOG_PATH=$HERE/TMP/frame.log
OPENING_TEXT=$'apple 10\npear 5\nplum 5'
SHOP_TEST_LIST=(delivery.json shop.sh)

open_shop() {
    #  RETURN: 0; a fresh, stocked database and an empty log stand.
    mkdir -p "$HERE/TMP"
    rm -rf "$DB_PATH" "$LOG_PATH"
    mkdir "$DB_PATH"
    echo "$OPENING_TEXT" > "$DB_PATH/opening"
    echo "$OPENING_TEXT" > "$DB_PATH/stock"
    : > "$DB_PATH/journal"
    : > "$LOG_PATH"
}

close_shop() {
    #  RETURN: 0; the database and the log are removed.
    rm -rf "$DB_PATH" "$LOG_PATH"
}

adds_up() {
    #  RETURN: 0, if every item's stock is its opening quantity plus its
    #             journal's movements;
    #          1, else.
    local item qty delta source
    local -A expected=() got=()
    while read -r item qty; do expected[$item]=$qty; done < "$DB_PATH/opening"
    while read -r item delta source; do (( expected[$item] += delta )); done < "$DB_PATH/journal"
    while read -r item qty; do got[$item]=$qty; done < "$DB_PATH/stock"
    for item in "${!expected[@]}"; do
        [[ ${got[$item]-} == "${expected[$item]}" ]] || return 1
    done
    return 0
}

check() {
    #  RETURN: 0; one line appended to the log for a run of a shop test
    #          '$2' (choice '$3') at '$1' -- nothing for any other test.
    local test=${2-} run verdict
    [[ " ${SHOP_TEST_LIST[*]} " == *" $test "* ]] || return 0
    run="$test ${3-}"; run=${run% }
    {   flock 9
        if adds_up; then verdict="stock adds up"; else verdict="STOCK BROKEN"; fi
    } 9> "$DB_PATH/lock"
    printf '%-6s %-15s %s\n' "$1" "$run" "$verdict" >> "$LOG_PATH"
}

case ${1-} in
    open)  open_shop ;;
    close) close_shop ;;
    check) check "${@:2:3}" ;;
    *)     echo "usage: fixture.sh open | close | check before|after <app> <choice>" >&2
           exit 2 ;;
esac
