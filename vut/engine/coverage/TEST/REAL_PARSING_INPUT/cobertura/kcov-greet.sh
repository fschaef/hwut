#!/bin/bash
# A branch taken and a branch not: argument "loud" shouts, absent stays calm.
mode="${1:-calm}"

if [ "$mode" = "loud" ]; then
    echo "HELLO, WORLD"
else
    echo "hello, world"
fi

for i in 1 2 3; do
    echo "count $i"
done
