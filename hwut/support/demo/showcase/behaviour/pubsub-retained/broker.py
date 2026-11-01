"""broker.py -- a small publish/subscribe broker with retained messages.

publish(topic, value)      the value is RETAINED: the last one per topic is
                           kept, and every subscriber gets it on subscribe
subscribe(sub, topic)      the retained value is queued first, then every
                           later publish, in publish order
unsubscribe(sub, topic)    when it returns ('gone' reported), no
                           further message reaches the subscriber: what is
                           still queued for it is PURGED, and reported so

Each subscriber has a queue and a delivery thread that calls its handler
(slow handlers do not hold up publishers). Every state change is reported
through 'say' inside the broker's lock, so the reports are causally
ordered: a delivery is never reported before its publish.
"""
import collections
import threading


class Broker:
    def __init__(self, say, deliver_s=0.0):
        self.say, self.deliver_s = say, deliver_s
        self.lock = threading.Condition()
        self.retained = {}                        # topic -> (seq, value)
        self.seq = collections.Counter()
        self.subs = {}                            # (sub, topic) -> True
        self.queue = {}                           # sub -> deque of (topic, seq, value)
        self.thread = {}

    def publish(self, topic, value):
        with self.lock:
            self.seq[topic] += 1
            seq = self.seq[topic]
            self.retained[topic] = (seq, value)
            self.say("pub %s %d %s" % (topic, seq, value))
            for (sub, t) in self.subs:
                if t == topic:
                    self.queue[sub].append((topic, seq, value))
            self.lock.notify_all()

    def subscribe(self, sub, topic, handler):
        with self.lock:
            self.subs[(sub, topic)] = True
            q = self.queue.setdefault(sub, collections.deque())
            self.say("sub %s %s" % (sub, topic))
            if topic in self.retained:
                q.append((topic,) + self.retained[topic])
            if sub not in self.thread:
                self.thread[sub] = threading.Thread(target=self._deliver, args=(sub, handler), daemon=True)
                self.thread[sub].start()
            self.lock.notify_all()

    def unsubscribe(self, sub, topic):
        with self.lock:
            self.say("unsub %s %s" % (sub, topic))
            del self.subs[(sub, topic)]
            self._purge(sub, topic)
            self.say("gone %s %s" % (sub, topic))

    def _purge(self, sub, topic):
        keep = collections.deque()
        for item in self.queue[sub]:
            if item[0] == topic:
                self.say("purge %s %s %d" % (sub, topic, item[1]))
            else:
                keep.append(item)
        self.queue[sub] = keep

    def _deliver(self, sub, handler):
        import time
        while True:
            with self.lock:
                while not self.queue[sub]:
                    self.lock.wait()
                topic, seq, value = self.queue[sub].popleft()
                self.say("deliver %s %s %d %s" % (sub, topic, seq, value))
            handler(topic, value)
            time.sleep(self.deliver_s)
