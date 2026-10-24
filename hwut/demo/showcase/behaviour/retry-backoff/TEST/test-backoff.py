#! /usr/bin/env python3
# @hwut {
#     title    = "Retry with exponential backoff and jitter: growing, capped, decorrelated"
#     choices {
#         herd-jitter   { features = ["decorrelated"]
#                         tolerance { constraints = ["lockstep == 0"] } }
#         herd-nojitter { features = ["herd-named"]
#                         tolerance { constraints = ["lockstep > 0"] } }
#         law           { features = ["window-law", "jitter-spread"]
#                         tolerance { constraints = ["spread >= 0.8", "sequences == 1000"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the retry delays the backoff module draws: four clients' schedules
         against a server that is down, or the extremes of 1000 sequences
REQUIREMENT  The delay before retry k lies in [w/2, w] with
             w = min(5000 ms, 100 ms * 2^k): it grows, never exceeds the cap,
             and is drawn at random inside that window, so that clients
             which failed together do not hammer the server together.

The unit is JavaScript ('../backoff.js', run by node) with its policy file
'../policy.json'. The test is Python. hwut sees neither language.

herd-jitter    four clients fail at t = 0 against a server that is down
               until 2.0 s; each retries after its drawn delays. One row per
               client ('x' a failed request, 'S' the one that succeeds, '.'
               waiting), one row for the server, and 'load': requests per
               50 ms column. The seed is FIXED (7): this choice is a picture,
               and a picture must be the same on every run.
herd-nojitter  the BROKEN FIXTURE '../backoff_nojitter.js' (delay = top of
               the window): the four rows are identical, the load row reads
               4 at every retry, and every retry coincides with another
               client's -- the thundering herd, accepted as the violation
               report, with the '!!' line.
               Both herd choices bind the clients whose whole retry schedule
               equals another client's, '((lockstep: N))': 'lockstep == 0'
               for herd-jitter, 'lockstep > 0' for herd-nojitter, so
               'hwut.accept' refuses a jitter that marches in step, or a
               nojitter that no longer shows the herd. (The 5 ms count stays
               plain text: a lawful jitter may bring two retries within 5 ms
               -- a jittered variant of the fixture gave 4 of 20.)
law            1000 sequences drawn from Math.random -- a different draw on
               every run. Per attempt, the shortest and the longest delay
               seen are printed as points (attempt, ms) in a point-cloud
               whose GOOD file carries the window law as its constraint:
               every point, whatever was drawn, must satisfy it. The jitter
               must also be real: the smallest spread over the attempts,
               (longest - shortest) / (w/2), is bound as ((spread: ..)) with
               the rule 'spread >= 0.8'.

WHY THESE TOLERANCES  The 'law' choice draws fresh numbers each run; the
recorded points mean nothing, the window rule means everything -- so the
point-cloud has no 'limit', only 'constraint={...}'. 'spread >= 0.8': with
1000 uniform draws the spread falls below 0.8 with probability about
1000 x 0.8^999, i.e. never; a code path that stops jittering gives 0.
The herd pictures need no tolerance: the seed is fixed. A reviewer reads
the client rows for alignment and the load row for 4s.
______________________________________________________________________________
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
POLICY = os.path.join(UNIT, "policy.json")
BASE, CAP, ATTEMPTS = 100, 5000, 8
DOWN_UNTIL, COLUMN_MS, SHOW_MS = 2000, 50, 4000


def draw(script, n, seed=None):
    cmd = ["node", os.path.join(UNIT, script), POLICY, str(n)] + ([str(seed)] if seed is not None else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [list(map(int, line.split())) for line in out.splitlines()]


def herd(script):
    seq_list = draw(script, 4, seed=7)
    col_n = SHOW_MS // COLUMN_MS
    load = [0] * col_n
    print("unit: %s; 4 clients fail at t = 0, the server is down until %.1f s; seed 7" % (script, DOWN_UNTIL / 1000))
    print()
    print("##! verbatim")
    ruler = "".join(("%.1f" % (c * COLUMN_MS / 1000)).ljust(10) if c % 10 == 0 else "" for c in range(col_n))
    print("s         %s" % ruler.rstrip())
    request_list = []
    for name, seq in zip("ABCD", seq_list):
        row = ["."] * col_n
        t, k = 0, 0
        while True:
            col = t // COLUMN_MS
            ok = t >= DOWN_UNTIL
            row[col] = "S" if ok else "x"
            load[col] += 1
            if t:
                request_list.append((t, name))
            if ok or k == ATTEMPTS:
                break
            t += seq[k]
            k += 1
        print("client %s  %s" % (name, "".join(row[:col + 1])))
    print("server    %s" % "".join("D" if c * COLUMN_MS < DOWN_UNTIL else "u" for c in range(col_n)))
    print("load      %s" % "".join(str(n) if n else "." for n in load))
    print("####")
    print("(one column per %d ms; x a failed request, S the one that succeeds, . waiting;" % COLUMN_MS)
    print(" server: D down, u up; load: requests per column)")
    print()
    print("delays drawn (ms):")
    for name, seq in zip("ABCD", seq_list):
        print("    client %s  %s" % (name, " ".join("%5d" % d for d in seq)))
    close_n = sum(any(abs(t - u) <= 5 and n != m for u, m in request_list) for t, n in request_list)
    print("retries (all requests after t = 0): %d; within 5 ms of another client's retry: %d%s"
          % (len(request_list), close_n, "  !! every one: a thundering herd" if close_n == len(request_list) else ""))
    lockstep_n = sum(seq_list.count(seq) > 1 for seq in seq_list)
    print("clients whose whole schedule equals another's: ((lockstep: %d)) of 4   law == 0   %s"
          % (lockstep_n, "kept" if not lockstep_n else "BROKEN"))


def law():
    seq_list = draw("backoff.js", 1000)
    print("1000 retry sequences from Math.random; base %d ms, cap %d ms, %d attempts"
          % (BASE, CAP, ATTEMPTS))
    print("per attempt k: the shortest and the longest delay drawn, as points (k, ms)")
    print("##! point-cloud constraint={y >= min(%d, %d * 2**x) / 2 and y <= min(%d, %d * 2**x)}"
          % (CAP, BASE, CAP, BASE))
    spread = 1.0
    for k in range(ATTEMPTS):
        column = [seq[k] for seq in seq_list]
        w = min(CAP, BASE * 2 ** k)
        print("%d %d" % (k, min(column)))
        print("%d %d" % (k, max(column)))
        spread = min(spread, (max(column) - min(column)) / (w / 2))
    print("####")
    print("(law of every point: w/2 <= ms <= w, w = min(%d, %d * 2^k))" % (CAP, BASE))
    print("sequences drawn: ((sequences: %d))   law == 1000   %s" % (len(seq_list), "kept" if len(seq_list) == 1000 else "BROKEN"))
    print("smallest spread, (longest - shortest) / (w/2) over the attempts: ((spread: %.3f))   law >= 0.8   %s"
          % (spread, "kept" if spread >= 0.8 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice == "herd-jitter":
        herd("backoff.js")
    elif choice == "herd-nojitter":
        herd("backoff_nojitter.js")
    elif choice == "law":
        law()
    else:
        print("choices: herd-jitter, herd-nojitter, law")
        sys.exit(1)
    print("<hwut-end>")
