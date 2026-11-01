#! /usr/bin/env python3
# @hwut {
#     title    = "Pub/sub broker: retained value first, publish order, silence after unsubscribe"
#     choices {
#         purge   { features = ["retained-first", "publish-order", "silence-after-gone", "none-lost"]
#                   tolerance { constraints = ["breaches == 0"] } }
#         nopurge { features = ["late-delivery-named"]
#                   tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what each subscriber of the broker received per topic: retained
         value first, order, delivery after unsubscribe, loss -- as counts
         and as the values delivered
REQUIREMENT  A subscriber first gets the value retained on its topic, then
             every later publish in publish order; once unsubscribe has
             returned, nothing more reaches it; and every value published
             while it was subscribed is delivered, or purged at unsubscribe
             -- never silently lost.

The unit is '../broker.py' (per-subscriber queues and delivery threads,
reports inside its lock). This application runs it under REAL threads:

    retained   temp 20, door closed
    A          subscribes to temp and door        B  subscribes to temp
    publishers temp 21..40 and door open/closed x10, concurrently, 1 ms apart
    B          unsubscribes from temp after temp 30 (the tenth publish)
    A          unsubscribes from both once everything is delivered

The deliveries take 10 ms each, and B's handler is a slow consumer: it
holds its first delivery (the retained 20) until B has unsubscribed. B
leaves after temp 30 and before temp 31 (the publisher waits for it). So
the backlog at unsubscribe is exactly temp 21..30 -- the race is made
CERTAIN under real threads, and the report can print counts.
'pubsub.pype' checks four laws per pair (subscriber, topic) and prints,
per pair, how many values were published while subscribed, delivered,
purged, delivered after unsubscribe, and lost; then one line per pair with
the values delivered, '^unsub' where unsubscribe returned.

purge    '../broker.py': unsubscribe purges the backlog (and reports what
         it purged). B/temp: delivered 1, purged 10, after-unsub 0.
nopurge  BROKEN FIXTURE '../broker_nopurge.py': the backlog is delivered
         after unsubscribe. B/temp: 'after-unsub 10 !!', and its value
         line reads '20(retained) ^unsub 21..30  !! after unsubscribe'.
         Accepted as the violation report.

HWUT CONCEPTS  pype with '<bol>'/'<eol>' anchors (needed: 'sub' is a
substring of 'unsub', and patterns match anywhere unless anchored), modes
LIVE -> DONE, a per-pair state machine kept in the shared namespace. The
GOOD file is compared exactly; 'hwut.run.stability --repeat=10' is steady.
The pype binds its number of breaches, '((breaches: N))': 'breaches == 0'
for purge, 'breaches > 0' for nopurge, so 'hwut.accept' refuses a
re-recording that breaks a law, or a nopurge that no longer shows it.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


def main(choice):
    Broker = __import__("broker" if choice == "purge" else "broker_nopurge").Broker
    pype = subprocess.Popen(["hwut.pype", os.path.join(HERE, "pubsub.pype")],
                            stdin=subprocess.PIPE, text=True)
    say_lock = threading.Lock()

    def say(text):
        with say_lock:
            pype.stdin.write(text + "\n")
            pype.stdin.flush()

    broker = Broker(say, deliver_s=0.010)
    ignore = lambda topic, value: None                            # noqa: E731
    ten_published, b_left = threading.Event(), threading.Event()
    a_in, b_in = threading.Event(), threading.Event()

    def b_handler(topic, value):                    # a slow consumer: it holds its
        b_left.wait(5.0)                            # first delivery until B has left

    say("scenario: retained temp 20, door closed; A subscribes to temp and door, B to temp; "
        "temp 21..40 and door open/closed x10 published concurrently; B unsubscribes after "
        "temp 30, its handler still busy with the retained 20")
    broker.publish("temp", "20")
    broker.publish("door", "closed")

    def subscribe_a():
        broker.subscribe("A", "temp", ignore)
        broker.subscribe("A", "door", ignore)
        a_in.set()

    def publish_temp():
        for value in range(21, 41):
            if value == 31:
                ten_published.set()
                b_left.wait(5.0)                    # B leaves before temp 31
            broker.publish("temp", str(value))
            time.sleep(0.001)

    def publish_door():
        for n in range(10):
            broker.publish("door", "open" if n % 2 == 0 else "closed")
            time.sleep(0.001)

    def b_comes_and_goes():
        broker.subscribe("B", "temp", b_handler)
        b_in.set()
        ten_published.wait(5.0)
        broker.unsubscribe("B", "temp")
        b_left.set()

    first = [threading.Thread(target=f) for f in (subscribe_a, b_comes_and_goes)]
    then = [threading.Thread(target=f) for f in (publish_temp, publish_door)]
    for thread in first:
        thread.start()
    a_in.wait(5.0)                                  # the subscriptions stand
    b_in.wait(5.0)
    for thread in then:
        thread.start()
    for thread in first + then:
        thread.join()
    while any(broker.queue.get(sub) for sub in ("A", "B")):
        time.sleep(0.005)
    time.sleep(0.010)                               # the last handler call returns
    broker.unsubscribe("A", "temp")
    broker.unsubscribe("A", "door")
    say("end")
    pype.stdin.close()
    return pype.wait()


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("purge", "nopurge"):
        print("choices: purge, nopurge")
        sys.exit(1)
    sys.exit(main(choice))
