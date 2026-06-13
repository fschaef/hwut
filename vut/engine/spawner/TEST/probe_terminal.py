"""Run from spawner/TEST/ in your tree:  python3 probe_terminal.py
Reports your event terminal's real peer-down API so the test and the
watchdog can be fixed against it."""
import config  # noqa: F401
from vut.engine.event.terminal import EventTerminal

names = [n for n in dir(EventTerminal) if "peer_down" in n]
print("peer_down public methods:", [n for n in names if not n.startswith("_")])

# instance attribute names (need an instance; use a dummy ecp if cheap,
# else just scan __init__ source)
import inspect, re
src = inspect.getsource(EventTerminal.__init__)
attrs = sorted(set(re.findall(r"self\.(_?peer_down\w*)", src)))
print("peer_down attributes set in __init__:", attrs)

# show the setter/adder signature(s)
for n in names:
    obj = getattr(EventTerminal, n, None)
    if callable(obj):
        try:
            print("  %-28s %s" % (n, inspect.signature(obj)))
        except (ValueError, TypeError):
            print("  %-28s (no signature)" % n)
