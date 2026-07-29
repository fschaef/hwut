"""A MOCK IDE CLIENT -- the smallest thing that speaks the protocol.

Reads DOWN messages as JSON lines on stdin, dispatching on 'kind' and
never importing anything from vut. Answers one UP envelope on stdout.
"""
import json, sys

SIGNATURE = "vut-feed/1"
seen, material = [], None
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    message = json.loads(line)
    if message.get("signature") != SIGNATURE:      # checked BEFORE parsing
        sys.stderr.write("refusing signature %r\n" % message.get("signature"))
        sys.exit(2)
    if message["kind"] == "MaterialInst":
        material = message["field_db"]
        break
    seen.append(message["kind"])

intent = sys.argv[1] if len(sys.argv) > 1 else "commit"
nominal = None
if intent == "commit" and material is not None:
    nominal = "resolved by the client after %i DOWN items\n" % len(seen)
sys.stdout.write(json.dumps({"signature": SIGNATURE,
                             "intent":    intent,
                             "nominal":   nominal}) + "\n")
sys.stdout.flush()
