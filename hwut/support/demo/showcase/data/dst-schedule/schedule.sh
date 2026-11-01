#! /bin/bash
# schedule.sh -- when does a job run? The shell version, built on GNU date.
#
#     schedule.sh daily   <zone> <first-day> <n> <HH:MM>
#     schedule.sh monthly <zone> <first-month> <n> <day>
#
# Prints one run per line: local time, zone abbreviation, UTC offset, UTC.
mode=$1; export TZ=$2; first=$3; n=$4; arg=$5
fmt='+%Y-%m-%d %H:%M %Z %z'
for ((k = 0; k < n; k++)); do
    if [ "$mode" = daily ]; then
        day=$(date -d "$first +$k day" +%F)
        stamp=$(date -d "$day $arg" +%s) || continue
    else
        stamp=$(date -d "$first-$arg +$k month" +%s) || continue
    fi
    echo "$(date -d "@$stamp" "$fmt") $(date -u -d "@$stamp" +%Y-%m-%dT%H:%MZ)"
done
