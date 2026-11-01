#! /usr/bin/env python3
# @hwut {
#     title    = "Work queue, 4 worker threads: every job done exactly once, in any order"
#     features = ["exactly-once", "causal-order"]
#     choices {
#         quick-jobs     { caps { timeout_sec = 20 }
#                          tolerance { constraints = ["breaches == 0"] } }
#         slow-heartbeat { caps { timeout_sec = 20 } features = ["exactly-once", "causal-order", "lease-extended"]
#                          tolerance { constraints = ["breaches == 0"] } }
#         slow-no-touch  { caps { timeout_sec = 20 } features = ["double-work-named"]
#                          tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  how often each of 24 jobs was taken, done and redelivered by the
         queue's workers, under one job-duration scenario
REQUIREMENT  Every job put into the queue is done exactly once; no job is
             taken before it was queued; nothing is queued after close. The
             order in which jobs are taken and done is free.

The unit is '../jobqueue.py', a queue with at-least-once delivery: a job not
acknowledged within the visibility timeout (200 ms) goes back to the queue.
This test application starts a producer thread (24 jobs, random gaps) and 4
worker threads (random job durations), and REPORTS what happens as it
happens -- the queue reports inside its own lock, so the stream is causally
ordered, but the interleaving of the threads differs on every run.

The stream goes into 'queue.pype', the LAW as modes OPEN -> CLOSED ->
STOPPED. The pype prints only what does not depend on the interleaving: a
grid of counts per job (taken / done / redelivered), the breaches sorted,
the jobs whose lease was extended (the heartbeat, from the queue's own
'lease extended' report), and the number of breaches bound as
'((breaches: N))' beside its law and a verdict word. The scenario is the
first line. It, not this program, prints <hwut-end>.

quick-jobs      1..15 ms per job: no lease runs out, every count is 1.
slow-heartbeat  job 7 takes 300 ms the first time (a cold cache); its
                worker touches the lease every 50 ms: still exactly once.
slow-no-touch   the same slow job WITHOUT the heartbeat: the lease runs out
                after 200 ms, job 7 is redelivered, a second worker does it
                too, and the first worker's late acknowledgement is stale.
                The GOOD file is the accepted report: 'done 2' under job 7,
                'BREACH: job 7 done 2 times'. Timing margins are 100 ms on
                either side, so the outcome is the same on every run.

HWUT CONCEPTS  pype: the law stated as modes over a nondeterministic event
stream; the GOOD file holds the order-free conclusion, compared exactly.
The binding carries the verdict into hwut's judgment: 'breaches == 0' for
the lawful choices, 'breaches > 0' for slow-no-touch -- 'hwut.accept'
refuses a re-recording that breaks the law, or hides the known breach.
'hwut.run.stability --repeat=10' agrees on every key. The choices get 20 s
(a 300 ms job and a reaper loop are the slowest things here).
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from jobqueue import JobQueue                                    # noqa: E402

JOB_N, WORKER_N, SLOW_JOB = 24, 4, 7


def main(choice):
    pype = subprocess.Popen(["hwut.pype", os.path.join(HERE, "queue.pype")],
                            stdin=subprocess.PIPE, text=True)
    say_lock = threading.Lock()

    def say(text):
        with say_lock:
            pype.stdin.write(text + "\n")
            pype.stdin.flush()

    say("scenario: %d jobs, %d workers, lease 200 ms; %s" % (JOB_N, WORKER_N, {
        "quick-jobs": "every job 1..15 ms",
        "slow-heartbeat": "job 7 takes 300 ms the first time, its worker extends the lease every 50 ms",
        "slow-no-touch": "job 7 takes 300 ms the first time, no heartbeat"}[choice]))
    queue = JobQueue(say, visibility_s=0.2)
    first_time = {SLOW_JOB: True}

    def worker():
        while True:
            got = queue.take()
            if got is None:
                return
            job, receipt = got
            slow = choice != "quick-jobs" and first_time.pop(job, False)
            duration = 0.3 if slow else random.uniform(0.001, 0.015)
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
                if choice == "slow-heartbeat" and time.monotonic() < deadline:
                    queue.touch(job, receipt)
            say("done %d" % job)
            queue.ack(job, receipt)

    def producer():
        for job in range(1, JOB_N + 1):
            time.sleep(random.uniform(0.0, 0.005))
            queue.put(job)
        queue.close()

    pool = [threading.Thread(target=worker) for _ in range(WORKER_N)]
    pool.append(threading.Thread(target=producer))
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    say("workers stopped")
    pype.stdin.close()
    return pype.wait()


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("quick-jobs", "slow-heartbeat", "slow-no-touch"):
        print("choices: quick-jobs, slow-heartbeat, slow-no-touch")
        sys.exit(1)
    random.seed(time.time_ns())
    sys.exit(main(choice))
