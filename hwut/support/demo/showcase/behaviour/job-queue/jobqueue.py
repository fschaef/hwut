"""jobqueue.py -- a work queue with at-least-once delivery (the SQS model).

A job taken by a worker is IN FLIGHT until the worker acknowledges it. If
no acknowledgement comes within the visibility timeout, a reaper puts the
job back, and another worker gets it. A worker on a long job extends its
lease with touch(). Every state change is reported through 'say' INSIDE
the queue's lock, so the reports are in causal order: a job is never
reported taken before it was reported queued.
"""
import collections
import threading
import time


class JobQueue:
    def __init__(self, say, visibility_s=0.2):
        self.say = say
        self.visibility_s = visibility_s
        self.lock = threading.Condition()
        self.ready = collections.deque()
        self.in_flight = {}                     # job -> (lease deadline, receipt)
        self.closed = False
        self.receipt_n = 0

    def put(self, job):
        with self.lock:
            self.ready.append(job)
            self.say("queued %d" % job)
            self.lock.notify()

    def close(self):
        with self.lock:
            self.closed = True
            self.say("queue closed")
            self.lock.notify_all()

    def take(self):
        """RETURN: (job, receipt), or None when closed and drained."""
        with self.lock:
            while True:
                self._reap()
                if self.ready:
                    job = self.ready.popleft()
                    self.receipt_n += 1
                    self.in_flight[job] = (time.monotonic() + self.visibility_s, self.receipt_n)
                    self.say("taken %d" % job)
                    return job, self.receipt_n
                if self.closed and not self.in_flight:
                    return None
                self.lock.wait(0.01)

    def touch(self, job, receipt):
        with self.lock:
            if self.in_flight.get(job, (0, None))[1] == receipt:
                self.in_flight[job] = (time.monotonic() + self.visibility_s, receipt)
                self.say("lease extended %d" % job)

    def ack(self, job, receipt):
        with self.lock:
            if self.in_flight.get(job, (0, None))[1] == receipt:
                del self.in_flight[job]
                self.say("acked %d" % job)
            else:
                self.say("stale ack %d" % job)
            self.lock.notify_all()

    def _reap(self):
        now = time.monotonic()
        for job, (deadline, _) in list(self.in_flight.items()):
            if deadline < now:
                del self.in_flight[job]
                self.ready.append(job)
                self.say("redelivered %d" % job)
