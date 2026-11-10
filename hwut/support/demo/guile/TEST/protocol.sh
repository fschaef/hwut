#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "Demo: an order law, stated as modes (a pype)"
#     features = ["demo-guile", "demo-guile+cover-order-law-by-pype", "demo-guile+cover-pype-owns-terminal-token"]
#     choices { clean  { }
#               broken { features = ["demo-guile+cover-law-breach-verdict"] }
#               slow   { features = ["demo-guile+cover-pype-tick", "demo-guile+cover-pype-time-guard"] } }
# }
#
# Five clients talk to a service at once. The order of the lines is the
# scheduler's. 'protocol.pype' holds the LAW -- every request answered,
# once, before shutdown; nothing before its request; nothing after
# shutdown -- and prints one verdict per exchange, sorted. The producer
# reports as it happens and prints no '<hwut-end>': the pype's '<eof>'
# does (pype manual 1b).
#
# 'broken' feeds the same pype a stream that breaks the law on purpose --
# answered twice, never answered, an answer without its request, a request
# after shutdown. The pype names each breach and says 'law: BROKEN'; that
# report is the GOOD.
#
# 'slow' answers request 2 only after 3 s. The pype is fed LIVE, so its
# clock is the service's: 'tick:' wakes it while no line arrives, and a
# wait guard marks a request open for over 1 s as late. (A pype named in
# a header reads the output after the run, all at once -- time is no
# input there.)
HERE=$(cd "$(dirname "$0")" && pwd)
#  THE PYPE IS THE FACE ON PATH in an installed hwut, and a copy written
#  by the demonstration's face stands anywhere; in the clone, the module below.
if command -v hwut.pype > /dev/null 2>&1; then
    pype() { hwut.pype "$@"; }
else
    ROOT=$(cd "$HERE/../../../../.." && pwd)
    export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
    pype() { python3 -m hwut.services.pype "$@"; }
fi

producer() {
    #  THE PRODUCER IS SCHEME: five clients, each a Guile thread, report
    #  as they happen; a line is written whole, under one mutex.
    guile --no-auto-compile /dev/stdin <<'SCM'
(use-modules (ice-9 threads))
(set! *random-state* (seed->random-state (let ((t (gettimeofday))) (+ (* (car t) 1000000) (cdr t)))))
(define lock (make-mutex))
(define (say text)
  "RETURN: unspecified. 'text' and a newline on stdout, flushed, whole."
  (with-mutex lock (display text) (newline) (force-output)))
(define (nap)
  "RETURN: unspecified. A pause drawn from 0 .. 20 ms."
  (usleep (random 20000)))
(define (client n)
  "RETURN: unspecified. Client 'n' asks, and is answered."
  (nap) (say (string-append "request " (number->string n)))
  (nap) (say (string-append "response " (number->string n))))
(for-each join-thread (map (lambda (n) (call-with-new-thread (lambda () (client n)))) (iota 5 1)))
(say "shutdown")
SCM
}

breaking() {
    printf '%s\n' "request 1" "response 1" "response 1" "request 2" \
                   "response 3" "shutdown" "request 4"
}

slow() {
    echo "request 1"; echo "response 1"
    echo "request 2"; echo "request 3"; echo "response 3"
    sleep 3
    echo "response 2"; echo "shutdown"
}

case "$1" in
    clean)  producer | pype "$HERE/protocol.pype" ;;
    broken) breaking | pype "$HERE/protocol.pype" ;;
    slow)   slow     | pype "$HERE/protocol.pype" ;;
    *)      echo "choices: clean, broken, slow"; exit 1 ;;
esac
