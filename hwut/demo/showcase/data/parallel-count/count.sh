#! /bin/bash
# count.sh FILE -- the map step: count the words of one file, and say so.
echo "start $(basename "$1")"
n=$(wc -w < "$1")
sleep "0.$((RANDOM % 3 + 2))"           # the work takes a while: 0.2..0.4 s, far longer
                                        # than starting a worker, so 12 workers started
                                        # at once are all in flight together
echo "count $(basename "$1") $n"
echo "done $(basename "$1")"
