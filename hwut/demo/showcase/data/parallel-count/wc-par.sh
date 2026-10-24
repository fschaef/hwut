#! /bin/bash
# wc-par.sh DIR -- count the words of DIR/*.txt, four files at a time.
#
# The map step (count.sh) runs on at most four files at once; its lines
# are passed on as the workers write them. The reduce step adds the counts
# once every worker has finished and prints 'total <n>' last.
HERE=$(cd "$(dirname "$0")" && pwd)
printf '%s\0' "$1"/*.txt | xargs -0 -n 1 -P 4 "$HERE/count.sh" \
    | awk '{ print; fflush() } $1 == "count" { sum += $3 } END { print "total " sum }'
