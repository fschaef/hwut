"""eventstore_noversion.py -- BROKEN FIXTURE: the store after someone dropped
the version check ('conflicts were rare and the retries slowed us down').
Two writers that read the same version both append, both with the same
sequence number -- the last-writer-wins race of every first event store.
"""
import threading

from eventstore import Conflict  # noqa: F401  (same interface)


class EventStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.stream_db = {}

    def load(self, stream):
        with self.lock:
            return list(self.stream_db.get(stream, []))

    def append(self, stream, expected_version, event):
        with self.lock:                                   # <-- no check
            self.stream_db.setdefault(stream, []).append(dict(event, seq=expected_version + 1))
