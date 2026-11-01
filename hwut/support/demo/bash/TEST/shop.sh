#! /usr/bin/env bash
#
# @hwut {
#     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
#     tolerance { stderr_ignored = true }
#     choices {
#         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
#         report { features = ["output-file", "keyed-table-separator", "dependency",
#                              "frame-scripts", "test-scripts", "stderr-ignored"]
#                  output   = ["<stdout>", "stock.csv"] }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  the stock of a small shop: a delivery comes in, three clerks sell
#          at once, and the stock is reported.
# REQUIREMENT  Every movement of the stock is journalled, so that the stock
#              always ADDS UP: opening quantity plus the journal's movements.
#
# 'shop.py' of the Python demonstration, in bash. THE DIRECTORY ARRANGES WHAT
# NO SINGLE TEST CAN -- in 'hwut.conf' beside this file, read it first:
# 'on_entry'/'on_exit' ('fixture.sh open'/'close'), 'on_before_test'/
# 'on_after_test' ('fixture.sh check ...', into 'TMP/frame.log'), 'apps'
# ('delivery.json' is a test without a header: 'shop.sh deliver
# delivery.json'), 'collision' (the delivery and the sale both write the
# database; hwut never runs them at once), 'dependency' ('shop.sh report'
# runs after both).
#
# THE DATABASE is 'fixture.sh's: a directory of text tables, one writer at
# a time by 'flock' on its 'lock' -- bash has no SQLite. A writer that waits
# longer than 10 s fails with 'database is locked', as SQLite's.
#
# STDERR  every statement on the database is logged on stderr, as a server
# would; the header says 'stderr_ignored = true'.
#
# CHOICES
#
# sell     three clerks sell at once, each in a background subshell. The
#          sales are printed as '##! table unordered sep={;}'.
# report   the stock, as '##! table key=0 sep={;}', and the same rows written
#          to 'stock.csv' ('output' names it; its GOOD is its own); then the
#          frame log of the shop's tests.
# deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
#          delivery note: every line on the stock and into the journal, in
#          one transaction.
#______________________________________________________________________________
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DB_PATH=$HERE/TMP/shop.db
LOG_PATH=$HERE/TMP/frame.log

#  What each clerk sells, one item per sale.
CLERK_NAMES=(anna ben chloe)
declare -A CLERK_MAP=([anna]="apple apple pear" [ben]="apple plum" [chloe]="apple")

connect() {
    #  RETURN: 0, the shop's database stands;
    #          exits 1 where it does not: 'on_entry' writes it.
    [[ -d $DB_PATH ]] && return 0
    echo "shop.sh: no $DB_PATH -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'" >&2
    exit 1
}

sql() {
    #  RETURN: 0; the statement '$*' is logged on stderr.
    echo "sql: $*" >&2
}

stock_moved() {
    #  RETURN: 0; the stock file holds the stock of item '$1' changed by
    #          '$2' -- written aside and renamed, so no reader sees half.
    #  The caller holds the lock.
    local item qty
    while read -r item qty; do
        [[ $item == "$1" ]] && qty=$(( qty + $2 ))
        echo "$item $qty"
    done < "$DB_PATH/stock" > "$DB_PATH/stock.$$"
    mv -f "$DB_PATH/stock.$$" "$DB_PATH/stock"
}

transaction() {
    #  RETURN: 0, the moves '$2...' ('item:delta' each) are on the stock and
    #             in the journal, as from source '$1', in one transaction;
    #          1, the lock was not had within 10 s ('database is locked').
    local source=$1 move; shift
    {   sql "BEGIN IMMEDIATE"
        flock -w 10 9 || { echo "database is locked" >&2; return 1; }
        for move; do
            sql "UPDATE stock SET qty = qty + ${move#*:} WHERE item = '${move%%:*}'"
            stock_moved "${move%%:*}" "${move#*:}"
            sql "INSERT INTO journal VALUES ('${move%%:*}', ${move#*:}, '$source')"
            echo "${move%%:*} ${move#*:} $source" >> "$DB_PATH/journal"
        done
        sql "COMMIT"
    } 9> "$DB_PATH/lock"
}

deliver() {
    #  RETURN: 0; the delivery note in file '$1' is booked and printed.
    #  JSON IS READ BY PATTERN: bash has no JSON parser, and the note has
    #  one shape -- 'note', 'supplier', 'lines' of '{ "item", "qty" }'.
    local text note supplier rest
    local -a item_list=() qty_list=() move_list=()
    text=$(< "$1")
    [[ $text =~ \"note\":[[:space:]]*\"([^\"]*)\" ]]     && note=${BASH_REMATCH[1]}
    [[ $text =~ \"supplier\":[[:space:]]*\"([^\"]*)\" ]] && supplier=${BASH_REMATCH[1]}
    rest=$text
    while [[ $rest =~ \"item\":[[:space:]]*\"([^\"]*)\"[[:space:]]*,[[:space:]]*\"qty\":[[:space:]]*([0-9]+) ]]; do
        item_list+=("${BASH_REMATCH[1]}") qty_list+=("${BASH_REMATCH[2]}")
        move_list+=("${BASH_REMATCH[1]}:${BASH_REMATCH[2]}")
        rest=${rest#*"${BASH_REMATCH[0]}"}
    done
    connect
    transaction "$note" "${move_list[@]}" || exit 1
    echo "delivery note $note from $supplier:"
    local i
    for (( i = 0; i < ${#item_list[@]}; ++i )); do
        printf '    %-6s +%d\n' "${item_list[i]}" "${qty_list[i]}"
    done
}

sell() {
    #  RETURN: 0; three clerks sold at once, every sale printed; exits 1
    #          where a sale failed.
    local scratch name item
    connect
    scratch=$(mktemp -d)
    : > "$scratch/sales"; : > "$scratch/errors"
    for name in "${CLERK_NAMES[@]}"; do
        (   for item in ${CLERK_MAP[$name]}; do
                if transaction "$name" "$item:-1"; then echo "$item;1" >> "$scratch/sales"
                else echo "$name: database is locked" >> "$scratch/errors"; exit 1
                fi
            done ) &
    done
    wait
    if [[ -s $scratch/errors ]]; then
        echo "shop.sh: a sale failed -- $(paste -sd';' "$scratch/errors")" >&2
        rm -rf "$scratch"
        exit 1
    fi
    echo "sales, item;qty -- in the order the clerks booked them:"
    echo "##! table unordered sep={;}"
    cat "$scratch/sales"
    echo "####"
    rm -rf "$scratch"
}

report() {
    #  RETURN: 0; the stock and the frame log printed, 'stock.csv' written.
    local -a row_list line_list
    local line
    connect
    sql "SELECT item, qty FROM stock ORDER BY qty, item"
    mapfile -t row_list < <(LC_ALL=C sort -k2,2n -k1,1 "$DB_PATH/stock")
    { echo "item;qty"; LC_ALL=C sort -k1,1 "$DB_PATH/stock" | tr ' ' ';'; } > "$HERE/stock.csv"
    echo "stock, item;qty (also written to stock.csv):"
    echo "##! table key=0 sep={;}"
    for line in "${row_list[@]}"; do echo "${line/ /;}"; done
    echo "####"
    mapfile -t line_list < "$LOG_PATH"
    echo "the frame, around the delivery and the sale:"
    echo "##! potpourri"
    for line in "${line_list[@]}"; do [[ $line == *"shop.sh report"* ]] || echo "${line%"${line##*[! ]}"}"; done
    echo "####"
    for line in "${line_list[@]}"; do [[ $line == *"shop.sh report"* ]] && echo "${line%"${line##*[! ]}"}"; done
}

case ${1-} in
    deliver) deliver "$2" ;;
    sell)    sell ;;
    report)  report ;;
    *)       echo "choices: sell, report"; exit 1 ;;
esac
echo "<hwut-end>"
