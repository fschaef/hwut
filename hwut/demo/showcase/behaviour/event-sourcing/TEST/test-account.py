#! /usr/bin/env python3
# @hwut {
#     title    = "Event-sourced account: two clerks race, the replay keeps the lifecycle and the balance"
#     choices {
#         versioned   { features = ["no-overdraft", "seq-contiguous", "lifecycle", "conflict-redecided"]
#                       tolerance { constraints = ["breaches == 0"] } }
#         unversioned { features = ["race-named"]
#                       tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the outcome of each command two clerks send to one account, and the
         ledger replayed from the event store afterwards
REQUIREMENT  Replaying an account's events always walks its lifecycle
             (opened -> active <-> frozen -> closed), with sequence numbers
             1, 2, 3, ... and a balance that never drops below zero -- even
             when two clerks withdraw at the same moment.

The unit is '../account.py' (the aggregate: state is derived from events, a
command becomes one event) on the event store '../eventstore.py', which
appends only at the version a command was decided on (optimistic
concurrency). This application plays eleven commands; two of them are a
RACE: two clerk threads withdraw 70 from a balance of 100, both deciding on
the same state (a barrier holds them between deciding and appending).
It reports each command's outcome as the clerk finishes, then the replay.

'account.pype' is the LAW as modes: COMMANDS (outcomes, counted -- the
clerks finish in any order), then the replay through NEW, ACTIVE, FROZEN,
CLOSED, each mode knowing which events it may see. The ledger is printed
row by row (the replay is ordered by the store), with the balance as a bar.

versioned    one clerk's append wins, the other meets a version conflict,
             decides again on the fresh state and is refused for
             insufficient funds. The ledger ends at zero, closed.
unversioned  the BROKEN FIXTURE '../eventstore_noversion.py': both appends
             go in, both as seq 3; the balance shows '!! below zero', the
             close is refused. Accepted as the violation report: three
             BREACH lines, sorted. Which clerk wins differs per run; the
             report does not, because both withdraw the same amount.

HWUT CONCEPTS  pype beyond 'order-free': modes as the states of a business
object, mode switches on events, a '<bol>' anchor, a helper function
defined in '<bof>' and shared by every mode. The GOOD file is compared
exactly; 'hwut.run.stability' agrees on every key. The pype binds the
number of breaches, '((breaches: N))': 'breaches == 0' for versioned,
'breaches > 0' for unversioned, so 'hwut.accept' refuses a re-recording
that breaks the law, or a fixture that no longer shows the race.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import account                                                    # noqa: E402

SCRIPT = [("open", 0), ("deposit", 100), "RACE", ("freeze", 0), ("deposit", 20),
          ("withdraw", 10), ("unfreeze", 0), ("withdraw", 50), ("close", 0), ("deposit", 5)]


def main(choice):
    EventStore = __import__("eventstore" if choice == "versioned" else "eventstore_noversion").EventStore
    store = EventStore()
    pype = subprocess.Popen(["hwut.pype", os.path.join(HERE, "account.pype")],
                            stdin=subprocess.PIPE, text=True)
    say_lock = threading.Lock()

    def say(text):
        with say_lock:
            pype.stdin.write(text + "\n")
            pype.stdin.flush()

    def command(name, amount, between=None):
        outcome = account.handle(store, "acct-17", name, amount, between)
        say("command %s%s: %s" % (name, " %d" % amount if amount else "", outcome))

    say("scenario: " + ", ".join("%s%s" % (step[0], " %d" % step[1] if step[1] else "")
                                  if step != "RACE" else "two clerks withdraw 70 at once"
                                  for step in SCRIPT))
    for step in SCRIPT:
        if step != "RACE":
            command(*step)
            continue
        barrier = threading.Barrier(2)
        clerk_list = [threading.Thread(target=command, args=("withdraw", 70, barrier.wait))
                      for _ in range(2)]
        for clerk in clerk_list:
            clerk.start()
        for clerk in clerk_list:
            clerk.join()

    say("replay")
    for event in store.load("acct-17"):
        say("event %d %s%s" % (event["seq"], event["type"],
                               " %d" % event["amount"] if "amount" in event else ""))
    pype.stdin.close()
    return pype.wait()


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("versioned", "unversioned"):
        print("choices: versioned, unversioned")
        sys.exit(1)
    sys.exit(main(choice))
