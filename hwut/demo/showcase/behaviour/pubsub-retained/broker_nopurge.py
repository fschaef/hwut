"""broker_nopurge.py -- BROKEN FIXTURE: the broker before the purge was
written. unsubscribe() removes the subscription and reports 'unsubscribed'
-- but what is already queued for the subscriber is still delivered after
that, by its delivery thread. Under light load nobody sees it.
"""
from broker import Broker as _Broker


class Broker(_Broker):
    def _purge(self, sub, topic):
        pass                                      # <-- the missing purge
