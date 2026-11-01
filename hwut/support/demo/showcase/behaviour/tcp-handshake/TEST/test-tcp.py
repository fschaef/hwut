#! /usr/bin/env python3
# @hwut {
#     title    = "TCP endpoint: every transition is an edge of RFC 793's state diagram"
#     features = ["rfc-edges", "reaches-closed"]
#     choices {
#         client-closes      { tolerance { constraints = ["outside_rfc == 0"] } }
#         server-closes      { tolerance { constraints = ["outside_rfc == 0"] } }
#         simultaneous-close { features = ["rfc-edges", "reaches-closed", "closing-state"]
#                              tolerance { constraints = ["outside_rfc == 0"] } }
#         fastclose-patch    { features = ["violation-named"]
#                              tolerance { constraints = ["outside_rfc > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the state changes and segments of two TCP endpoints for one
         scenario, drawn as a sequence diagram against RFC 793
REQUIREMENT  Every state change of the endpoint is an edge of the RFC 793
             connection diagram (fig. 6), with the segments the RFC says to
             send; and a connection, once closed by both sides, ends in
             CLOSED -- through TIME_WAIT on the side that closed first.

Two endpoints of '../tcp_fsm.py' are wired by a lossless in-order network.
A scenario is a list of application calls; '~' delivers every segment in
flight (and the answers they provoke) until the wire is quiet. The output:

  1. a SEQUENCE DIAGRAM, client | wire | server, one row per transition:
     the new state on the side that moved, the segment it sent as an arrow,
     and the cause on the right ('rcv FIN', 'close()'); a row whose
     transition is outside RFC 793 ends in '!!';
  2. the JUDGEMENT of every transition against the RFC table that this
     test holds as its specification: the number judged, and one '!!' line
     per transition outside the RFC (the diagram already shows the rest --
     each thing is said once);
  3. the RFC edges this scenario walked, [x] / [ ] -- the coverage of the
     diagram, readable at a glance.

client-closes       open, one DATA exchange, the client closes first: the
                    client walks FIN_WAIT_1/2 and TIME_WAIT, the server
                    CLOSE_WAIT and LAST_ACK.
server-closes       the mirror image: the roles of the close swap sides.
simultaneous-close  both call close() before either FIN arrives: the FINs
                    cross on the wire and both ends pass CLOSING.
fastclose-patch     the BROKEN FIXTURE '../tcp_fsm_fastclose.py' (TIME_WAIT
                    skipped) under the client-closes scenario. The GOOD file
                    is the accepted violation report: one '!!' line naming
                    the transition and what RFC 793 says instead.

HWUT CONCEPTS  The diagram stands in '##! verbatim': in a picture, the
column a state stands in IS the information (client or server), and the
default whitespace tolerance would fold it away. Nothing varies between
runs; no other tolerance is needed. The number of transitions outside
RFC 793 is a constraint binding, '((outside_rfc: N))': 'outside_rfc == 0'
for the three scenarios on '../tcp_fsm.py', 'outside_rfc > 0' for the
fastclose patch -- 'hwut.accept' refuses a re-recording with an edge the
RFC does not have, or a patch that no longer shows its violation. A
reviewer reads the diagram top-down like a whiteboard sketch and checks
the '!!' marks and the [x] marks.
______________________________________________________________________________
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

#  THE SPECIFICATION: RFC 793, fig. 6 (plus the data-transfer self-loops).
#  (state, cause) -> (next state, segments sent)
RFC_793 = [
    ("CLOSED",      "listen",  "LISTEN",      ""),
    ("CLOSED",      "connect", "SYN_SENT",    "SYN"),
    ("LISTEN",      "SYN",     "SYN_RCVD",    "SYN+ACK"),
    ("SYN_SENT",    "SYN+ACK", "ESTABLISHED", "ACK"),
    ("SYN_RCVD",    "ACK",     "ESTABLISHED", ""),
    ("ESTABLISHED", "send",    "ESTABLISHED", "DATA"),
    ("ESTABLISHED", "DATA",    "ESTABLISHED", "ACK"),
    ("ESTABLISHED", "ACK",     "ESTABLISHED", ""),
    ("ESTABLISHED", "close",   "FIN_WAIT_1",  "FIN"),
    ("ESTABLISHED", "FIN",     "CLOSE_WAIT",  "ACK"),
    ("FIN_WAIT_1",  "ACK",     "FIN_WAIT_2",  ""),
    ("FIN_WAIT_1",  "FIN",     "CLOSING",     "ACK"),
    ("FIN_WAIT_2",  "FIN",     "TIME_WAIT",   "ACK"),
    ("CLOSING",     "ACK",     "TIME_WAIT",   ""),
    ("TIME_WAIT",   "timeout", "CLOSED",      ""),
    ("CLOSE_WAIT",  "close",   "LAST_ACK",    "FIN"),
    ("LAST_ACK",    "ACK",     "CLOSED",      ""),
]
RFC_DB = dict(((s, c), (n, snd)) for s, c, n, snd in RFC_793)

SCENARIO_DB = {
    "client-closes":      "S:listen C:connect ~ C:send ~ C:close ~ S:close ~ C:timeout",
    "server-closes":      "S:listen C:connect ~ S:send ~ S:close ~ C:close ~ S:timeout",
    "simultaneous-close": "S:listen C:connect ~ C:close S:close ~ C:timeout S:timeout",
    "fastclose-patch":    "S:listen C:connect ~ C:send ~ C:close ~ S:close ~ C:timeout",
}
APP_CALL_SET = {"listen", "connect", "send", "close", "timeout"}


def cause_text(cause):
    return cause + "()" if cause in APP_CALL_SET else "rcv " + cause


def arrow(side, sent):
    """RETURN: the wire column, 26 wide: an arrow carrying 'sent'."""
    if sent == "REFUSED":
        return "      (refused)".ljust(26)
    if not sent:
        return " " * 26
    if side == "C":
        return ("--" + sent).ljust(24, "-") + "> "
    return " <" + (sent + "--").rjust(24, "-")


def play(module_name, scenario):
    Endpoint = __import__(module_name).Endpoint
    end_db = {"C": Endpoint("client"), "S": Endpoint("server")}
    wire = []                                  # (to-side, segment)
    walk = []                                  # (side, old, cause, new, sent)

    def act(side, cause):
        old = end_db[side].state
        try:
            sent_list = end_db[side].on(cause)
        except ValueError:                     # the unit refuses the cause
            walk.append((side, old, cause, old, "REFUSED"))
            return
        walk.append((side, old, cause, end_db[side].state, "+".join(sent_list)))
        for segment in sent_list:
            wire.append(("S" if side == "C" else "C", segment))

    for step in scenario.split():
        if step == "~":
            while wire:
                side, segment = wire.pop(0)
                act(side, segment)
        else:
            side, call = step.split(":")
            act(side, call)
    return walk, end_db


def main(choice):
    module_name = "tcp_fsm_fastclose" if choice == "fastclose-patch" else "tcp_fsm"
    walk, end_db = play(module_name, SCENARIO_DB[choice])

    print("scenario: %s" % SCENARIO_DB[choice])
    print("unit:     %s.py" % module_name)
    print()
    judged = []                                # (row, verdict or None)
    for side, old, cause, new, sent in walk:
        rfc_new, rfc_sent = RFC_DB.get((old, cause), (None, None))
        if (rfc_new, rfc_sent) == (new, sent) or (sent == "REFUSED" and rfc_new is None):
            judged.append(None)
        elif rfc_new is None:
            judged.append("RFC 793 has no edge for '%s' in %s" % (cause_text(cause), old))
        else:
            judged.append("RFC 793: %s --%s--> %s%s" % (old, cause_text(cause), rfc_new,
                                                        " sends " + rfc_sent if rfc_sent else ""))
    print("##! verbatim")
    print("%-12s %s %-12s %s" % ("client", "        the wire          ", "server", "cause"))
    print("%-12s %s %-12s %s" % ("------", "--------------------------", "------", "-----"))
    print(("%-12s %s %-12s" % ("CLOSED", " " * 26, "CLOSED")).rstrip())
    for (side, old, cause, new, sent), verdict in zip(walk, judged):
        left, right = (new, "") if side == "C" else ("", new)
        print(("%-12s %s %-12s %s%s" % (left, arrow(side, sent), right, cause_text(cause),
                                        "  !!" if verdict else "")).rstrip())
    print("####")
    print("(a row: the state an endpoint enters and the segment it sends; '!!' a transition outside RFC 793)")
    print()
    breach_n = sum(1 for v in judged if v)
    refused_n = sum(1 for w in walk if w[4] == "REFUSED")
    print("transitions judged against RFC 793: %d%s" % (len(walk), ", %d refused by the unit where the RFC has no edge either" % refused_n if refused_n else ""))
    for (side, old, cause, new, sent), verdict in zip(walk, judged):
        if verdict:
            print("    !! %s %s --%s--> %s, but %s" % ("client" if side == "C" else "server", old, cause_text(cause), new, verdict))
    print("end states: client %s, server %s" % (end_db["C"].state, end_db["S"].state))
    first = next(side for side, _, cause, _, _ in walk if cause == "close")
    passed_time_wait = any(side == first and new == "TIME_WAIT" for side, _, _, new, _ in walk)
    print("the side that closed first (%s) passed TIME_WAIT: %s" % ("client" if first == "C" else "server",
                                                                     "yes" if passed_time_wait else "!! NO"))
    print("transitions outside RFC 793: ((outside_rfc: %d))   law == 0   %s" % (breach_n, "kept" if not breach_n else "BROKEN"))
    print()

    taken = set((old, cause) for _, old, cause, new, sent in walk
                if RFC_DB.get((old, cause)) == (new, sent))
    print("RFC 793 edges walked by this scenario ([x] walked, [ ] not):")
    for s, c, n, snd in RFC_793:
        print(("    [%s] %-11s --%-12s--> %-11s %s"
               % ("x" if (s, c) in taken else " ", s, cause_text(c), n, ("sends " + snd) if snd else "")).rstrip())


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in SCENARIO_DB:
        print("choices: %s" % ", ".join(SCENARIO_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
