#! /usr/bin/env python3
# @hwut {
#     title    = "A pipe conversation with a threaded C server: potpourri or pype?"
#     choices {
#         live-potpourri   { features = ["same-lines"] }
#         live-pype        { features = ["answer-after-request", "answered-once"]
#                            tolerance { constraints = ["breaches == 0"] } }
#         replay-potpourri { features = ["potpourri-blind"] }
#         replay-pype      { features = ["early-answer-named"]
#                            tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the request/answer conversation between a client and the calcd
         server over a pipe (live, or a recorded transcript)
REQUIREMENT  The server answers every request exactly once, and never before
             the request was made; the answers may come in any order, and
             'bye' counts them.

The unit is C ('../calcd.c'): a request server on stdin/stdout with a pool
of three pthreads; each worker answers when it is done, so the answers
cross the requests differently on every run. This application is the
client: it sends eight requests with small pauses and reports the
conversation as it happens -- '> ' what it sent (reported BEFORE writing, so
no answer can be reported ahead of its request), '< ' what it read.

Two ways to make such a conversation comparable, side by side:

live-potpourri    the conversation framed as '##! potpourri': the same lines
                  must stand on both sides, in any order. Simple, and it
                  passes every run.
live-pype         the conversation through 'conversation.pype', the LAW: an
                  answer after its request, exactly once, bye counts. It
                  prints one row per request, sorted.
replay-potpourri  a recorded transcript of calcd 0.9 ('../transcripts/'): a
                  stale cache answered request 5 BEFORE it was sent. The
                  lines are the same multiset as a good run's -- so the
                  potpourri PASSES, and its GOOD file reads like a good
                  conversation. That green is the lesson of this choice: a
                  potpourri says 'order does not matter', and here some
                  order does.
replay-pype       the same transcript through the pype: request 5's row
                  reads 'once  !! one before its request'. Accepted as the
                  violation report. (A breach that belongs to a request
                  stands in its row; only the others get a BREACH line.)

WHEN TO USE WHICH  potpourri when the order carries no meaning at all (a
set printed from a hash map, workers' 'done' lines). pype when SOME order
matters (causality, once-only, nothing after the end) -- it states that
part as a law and drops the rest.

HWUT CONCEPTS  '##! potpourri' region; a pype script printing <hwut-end>
from its '<eof>' (the application prints it only where no pype stands).
The pype binds its number of breaches, '((breaches: N))': 'breaches == 0'
for live-pype, 'breaches > 0' for replay-pype, so 'hwut.accept' refuses a
re-recording that breaks the law, or a replay that no longer shows it. The
potpourri choices carry no such law on purpose: a potpourri cannot see
order, and replay-potpourri's green is the point.
Real threads: verified with 'hwut.run.stability --repeat=10'.
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
REQUEST_LIST = ["fib 20", "upper hello", "rev pipes", "len conversation",
                "fib 30", "upper hwut", "rev stressed", "len a"]


def live_conversation(say):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "calcd")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-O2", "-pthread", "-o", exe,
                               os.path.join(UNIT, "calcd.c")])
        server = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

        def reader():
            for line in server.stdout:
                say("< " + line.strip())

        listener = threading.Thread(target=reader)
        listener.start()
        for n, request in enumerate(REQUEST_LIST, 1):
            say("> req %d %s" % (n, request))
            server.stdin.write("req %d %s\n" % (n, request))
            server.stdin.flush()
            time.sleep(random.uniform(0.0, 0.006))
        server.stdin.write("quit\n")
        server.stdin.close()
        listener.join()
        server.wait()


def replay_conversation(say):
    with open(os.path.join(UNIT, "transcripts", "calcd-0.9.txt")) as fh:
        for line in fh:
            say(line.rstrip("\n"))


def main(choice):
    say_lock = threading.Lock()
    play = live_conversation if choice.startswith("live") else replay_conversation
    print("conversation: %s" % ("calcd.c live, %d requests, 0..6 ms apart" % len(REQUEST_LIST)
                                if choice.startswith("live") else "the recorded transcript transcripts/calcd-0.9.txt"),
          flush=True)
    if choice.endswith("pype"):
        pype = subprocess.Popen(["hwut.pype", os.path.join(HERE, "conversation.pype")],
                                stdin=subprocess.PIPE, text=True)

        def say(text):
            with say_lock:
                pype.stdin.write(text + "\n")
                pype.stdin.flush()
        play(say)
        pype.stdin.close()
        return pype.wait()

    line_list = []

    def say(text):
        with say_lock:
            line_list.append(text)
    play(say)
    print("##! potpourri")
    for line in line_list:
        if not line.startswith("< bye"):
            print(line)
    print("####")
    print(line_list[-1])
    print("(order not judged: a potpourri compares the lines as a set)")
    print("<hwut-end>")
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("live-potpourri", "live-pype", "replay-potpourri", "replay-pype"):
        print("choices: live-potpourri, live-pype, replay-potpourri, replay-pype")
        sys.exit(1)
    random.seed(time.time_ns())
    sys.exit(main(choice))
