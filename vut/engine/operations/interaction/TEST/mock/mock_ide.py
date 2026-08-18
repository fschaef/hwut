"""A MOCK IDE CLIENT -- the smallest thing that speaks the protocol.

Reads DOWN messages as JSON lines on stdin, dispatching on 'kind' and
never importing anything from vut. Answers one UP envelope per ROUND.

    python3 mock_ide.py commit
    python3 mock_ide.py cancel
    python3 mock_ide.py realign commit      <-- exercises the merge loop

Each argument is the intent for one round, in order; the last is repeated
if the hub asks again. A 'realign' answer APPENDS a line to the nominal it
was handed, so the round genuinely progresses -- the hub refuses a REALIGN
whose nominal is unchanged, and rightly so.

After answering a REALIGN the client keeps reading: the hub replies with a
FRESH DOWN generation on the same pipe and closes it only when the session
is really over.
"""
import json, sys

SIGNATURE = "vut-feed/1"

intent_list = sys.argv[1:] or ["commit"]
seen        = []          # DOWN kinds seen, across the whole session
round_n     = 0

for line in sys.stdin:
    line = line.strip()
    if not line: continue
    message = json.loads(line)
    if message.get("signature") != SIGNATURE:      # checked BEFORE parsing
        sys.stderr.write("refusing signature %r\n" % message.get("signature"))
        sys.exit(2)

    if message["kind"] != "MaterialInst":
        seen.append(message["kind"])
        continue

    material = message["field_db"]
    intent   = intent_list[min(round_n, len(intent_list) - 1)]
    round_n += 1

    nominal = None
    if intent == "commit":
        nominal = "resolved by the client after %i DOWN items\n" % len(seen)
    elif intent == "realign":
        #  An EDIT. The round must PROGRESS or the hub ends the session.
        nominal = material["nominal"] + "edit %i by the client\n" % round_n

    sys.stdout.write(json.dumps({"signature": SIGNATURE,
                                 "intent":    intent,
                                 "nominal":   nominal}) + "\n")
    sys.stdout.flush()
    #  NOT a break: a REALIGN is answered with another DOWN generation.
