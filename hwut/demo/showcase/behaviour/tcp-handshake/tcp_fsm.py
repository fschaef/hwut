"""tcp_fsm.py -- the connection state machine of a small TCP endpoint.

The UNIT UNDER TEST. An endpoint knows its state and reacts to two kinds of
cause: an application call ('listen', 'connect', 'send', 'close') and an
arriving segment ('SYN', 'SYN+ACK', 'ACK', 'FIN', 'DATA'), plus the 2MSL
timer ('timeout'). Each reaction returns the segments to send.
Written as if-chains, the way such code usually looks -- the specification
(the RFC 793 diagram) lives in the test, not here.
"""


class Endpoint:
    def __init__(self, name):
        self.name = name
        self.state = "CLOSED"

    def on(self, cause):
        """RETURN: list of segments to send. Changes self.state."""
        s = self.state
        if cause == "listen" and s == "CLOSED":
            self.state = "LISTEN"
            return []
        if cause == "connect" and s == "CLOSED":
            self.state = "SYN_SENT"
            return ["SYN"]
        if cause == "SYN" and s == "LISTEN":
            self.state = "SYN_RCVD"
            return ["SYN+ACK"]
        if cause == "SYN+ACK" and s == "SYN_SENT":
            self.state = "ESTABLISHED"
            return ["ACK"]
        if cause == "ACK" and s == "SYN_RCVD":
            self.state = "ESTABLISHED"
            return []
        if s == "ESTABLISHED":
            if cause == "send":
                return ["DATA"]
            if cause == "DATA":
                return ["ACK"]
            if cause == "ACK":
                return []
            if cause == "close":
                self.state = "FIN_WAIT_1"
                return ["FIN"]
            if cause == "FIN":
                self.state = "CLOSE_WAIT"
                return ["ACK"]
        if s == "FIN_WAIT_1":
            if cause == "ACK":
                self.state = "FIN_WAIT_2"
                return []
            if cause == "FIN":
                self.state = "CLOSING"
                return ["ACK"]
        if s == "FIN_WAIT_2" and cause == "FIN":
            self.state = "TIME_WAIT"
            return ["ACK"]
        if s == "CLOSING" and cause == "ACK":
            self.state = "TIME_WAIT"
            return []
        if s == "TIME_WAIT" and cause == "timeout":
            self.state = "CLOSED"
            return []
        if s == "CLOSE_WAIT" and cause == "close":
            self.state = "LAST_ACK"
            return ["FIN"]
        if s == "LAST_ACK" and cause == "ACK":
            self.state = "CLOSED"
            return []
        raise ValueError("%s: no reaction to '%s' in %s" % (self.name, cause, s))
