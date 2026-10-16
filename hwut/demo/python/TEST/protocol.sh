#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "Demo: an order law, stated as modes (a pype)"
#     features = ["demo-passes-on-every-run", "order-law-by-pype", "pype-owns-terminal-token"]
#     choices { clean { } }
# }
#
# Five clients talk to a service at once. The order of the lines is the
# scheduler's. 'protocol.pype' holds the LAW -- every request answered,
# once, before shutdown; nothing before its request; nothing after
# shutdown -- and prints one verdict per exchange, sorted. The producer
# reports as it happens and prints no '<hwut-end>': the pype's '<eof>'
# does (pype manual 1b).
HERE=$(cd "$(dirname "$0")" && pwd)
#  THE PYPE IS THE FACE ON PATH in an installed hwut, and a copy written
#  by 'hwut.demo.python' stands anywhere; in the clone, the module below.
if command -v hwut.pype > /dev/null 2>&1; then
    pype() { hwut.pype "$@"; }
else
    ROOT=$(cd "$HERE/../../../.." && pwd)
    export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
    pype() { python3 -m hwut.services.pype "$@"; }
fi

producer() {
    python3 - <<'PY'
import random, threading, time
lock = threading.Lock()
def say(text):
    with lock:
        print(text, flush=True)
def client(n):
    time.sleep(random.uniform(0.0, 0.02))
    say("request %d" % n)
    time.sleep(random.uniform(0.0, 0.02))
    say("response %d" % n)
pool = [threading.Thread(target=client, args=(n,)) for n in range(1, 6)]
for t in pool: t.start()
for t in pool: t.join()
say("shutdown")
PY
}

case "$1" in
    clean) producer | pype "$HERE/protocol.pype" ;;
    *)     echo "choices: clean"; exit 1 ;;
esac
