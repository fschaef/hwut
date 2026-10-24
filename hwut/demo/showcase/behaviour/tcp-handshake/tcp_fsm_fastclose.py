"""tcp_fsm_fastclose.py -- a BROKEN FIXTURE: the 'fast close' patch.

Somebody ran out of ports under load and 'fixed' it by closing at once when
the peer's FIN arrives in FIN_WAIT_2 -- skipping TIME_WAIT. The connection
still closes, every byte still arrives; only the state walk is wrong (late
duplicates of the old connection can now be taken for a new one).
"""
from tcp_fsm import Endpoint as _Endpoint


class Endpoint(_Endpoint):
    def on(self, cause):
        if self.state == "FIN_WAIT_2" and cause == "FIN":
            self.state = "CLOSED"            # <-- the 'optimisation'
            return ["ACK"]
        return _Endpoint.on(self, cause)
