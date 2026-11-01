#! /bin/bash
#
# @hwut {
#     title    = "SQL migrations: numbered without gaps or twins, each with a down that undoes its up"
#     features = ["sequence", "reversible"]
#     choices {
#         good   { tolerance { constraints = ["findings == 0"] } }
#         broken { tolerance { constraints = ["findings > 0"] } }
#     }
# }
#
# ____________________________________________________________________________
# SUBJECT  the ladder of one set of SQL migrations (good/broken): numbering,
#          up/down pairs, what each down drops
# REQUIREMENT for migrations/NNNN_<name>.up.sql / .down.sql
#   M1  the numbers run 0001, 0002, ... without a gap, and no number is used
#       twice (two branches merged, each with its own 0005: the order in
#       which they run is then the order of 'ls');
#   M2  every up has its down;
#   M3  the down undoes the up: every table, column and index the up creates
#       the down drops -- no more, no less.
#
# HOW: bash and awk read the SQL; no database is needed. 'IF [NOT] EXISTS'
# and UNIQUE are skipped, names are compared case-blind; a CREATE, DROP or
# ALTER statement the reader does not understand is itself a finding
# (UNREAD), so a misparse cannot pass as 'ok'. The output is the
# LADDER: one rung per migration, the up and the down as the two rails
# ([U]===[D]; a missing rail is '...'); a gap is a broken rung. Each rung
# says what the up creates and whether the down drops exactly that.
#
# CHOICES
#   good     six migrations, 0001..0006, each reversible; 0006 written with
#            IF [NOT] EXISTS.
#   broken   0003 vanished in a rebase (gap); 0004's down drops nothing;
#            two migrations carry the number 0005; 0006 has no down.
#
# HWUT CONCEPTS
#   constraints  'findings == 0' for good -- the requirement; 'findings > 0'
#                for broken -- the violation is reported, the ladder says
#                where.
#   exact lines  the ladder and the newest number.
#
# READING THE GOOD: every rung '[U]===[D]' and 'ok'; no broken rung.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
export LC_ALL=C
case "$1" in
    good|broken) ;;
    *) echo "choices: good, broken"; exit 1 ;;
esac
cd "$HERE/../$1/migrations" || exit 1

objects() {       # $1 = file, $2 = CREATE|DROP  -> 'table x', 'column t.c', 'index i'
    [ -f "$1" ] || return
    awk -v verb="$2" '
        { $0 = toupper($0); sub(/^[ \t]+/, ""); gsub(/ IF (NOT )?EXISTS /, " "); sub(/^CREATE UNIQUE /, "CREATE "); $0 = $0 }
        /^(CREATE|DROP|ALTER) / && $0 !~ /^(CREATE|DROP) (TABLE|INDEX) [A-Z_]+/ \
                                && $0 !~ /^ALTER TABLE [A-Z_]+ (ADD|DROP) COLUMN [A-Z_]+/ {
            if (verb == "UNREAD") print $1 " " $2 " " $3 }
        verb == "CREATE" && /^CREATE (TABLE|INDEX) / { sub(/\(.*/, "", $3); print tolower($2) " " tolower($3) }
        verb == "DROP"   && /^DROP (TABLE|INDEX) /   { sub(/;$/, "", $3); print tolower($2) " " tolower($3) }
        /^ALTER TABLE [A-Z_]+ (ADD|DROP) COLUMN [A-Z_]+/ {
            sub(/;$/, "", $6)
            if (($4 == "ADD" && verb == "CREATE") || ($4 == "DROP" && verb == "DROP"))
                print "column " tolower($3) "." tolower($6)
        }' "$1" | sort
}

echo "migrations of '$1'"
echo "rules: M1 no gap, no twin   M2 a down for every up   M3 the down drops what the up creates"
echo
echo "LADDER   [U] up   [D] down   ... missing   creates (up) -> dropped by the down?"
findings=0; expect=1; head=0; previous=""
for up in $(ls *.up.sql | sort); do
    number=${up%%_*}; name=${up#*_}; name=${name%.up.sql}; n=$((10#$number))
    while [ "$n" -gt "$expect" ]; do
        printf "  %04d  [ ]   [ ]  --------- M1 GAP: no migration %04d ----------\n" "$expect" "$expect"
        findings=$((findings + 1)); expect=$((expect + 1))
    done
    twin=""
    if [ "$number" = "$previous" ]; then twin="M1 TWIN: $number used twice"; findings=$((findings + 1)); fi
    down=${up%.up.sql}.down.sql
    created=$(objects "$up" CREATE | paste -sd, - | sed 's/,/, /g')
    unread=$( { objects "$up" UNREAD; objects "$down" UNREAD; } | paste -sd, - | sed 's/,/, /g')
    if [ -n "$unread" ]; then
        rung="[U]?? [D]"; verdict="M3 UNREAD: $unread"; findings=$((findings + 1))
    elif [ ! -f "$down" ]; then
        rung="[U]...   "; verdict="M2 NO DOWN"; findings=$((findings + 1))
    else
        rung="[U]===[D]"
        if [ "$(objects "$up" CREATE)" = "$(objects "$down" DROP)" ]; then
            verdict="ok"
        else
            missing=$(comm -23 <(objects "$up" CREATE) <(objects "$down" DROP) | paste -sd, - | sed 's/,/, /g')
            extra=$(comm -13 <(objects "$up" CREATE) <(objects "$down" DROP) | paste -sd, - | sed 's/,/, /g')
            verdict="${missing:+M3 NOT UNDONE: $missing}${missing:+${extra:+  }}${extra:+M3 DROPS MORE: $extra}"
            findings=$((findings + 1))
        fi
    fi
    if [ -n "$twin" ]; then
        [ "$verdict" = "ok" ] && verdict="$twin" || verdict="$verdict  $twin"
    fi
    printf "  %s  %s  %-20s %-36s %s\n" "$number" "$rung" "$name" "$created" "$verdict"
    previous=$number; expect=$((n + 1)); head=$n
done
echo
echo "newest migration: $head   ((findings: $findings))   law == 0   $([ $findings = 0 ] && echo kept || echo BROKEN)"
echo "<hwut-end>"
