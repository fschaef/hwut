"""eventstore.py -- an append-only event store with optimistic concurrency.

append(stream, expected_version, event) succeeds only if the stream is
still at 'expected_version' (the number of its events); otherwise it raises
Conflict, and the writer must reload and decide again. Events get the
sequence number expected_version + 1.
"""
import threading


class Conflict(Exception):
    pass


class EventStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.stream_db = {}

    def load(self, stream):
        with self.lock:
            return list(self.stream_db.get(stream, []))

    def append(self, stream, expected_version, event):
        with self.lock:
            event_list = self.stream_db.setdefault(stream, [])
            if len(event_list) != expected_version:
                raise Conflict("%s is at %d, not %d" % (stream, len(event_list), expected_version))
            event_list.append(dict(event, seq=expected_version + 1))
