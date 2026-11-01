"""grammar.py -- the command grammar of the service shell, as data.

Each nonterminal maps to its ALTERNATIVES; an alternative is a list of
symbols (nonterminals or quoted words). Every alternative is its own list
object: SelectionMarker tells alternatives apart by identity.
"""
GRAMMAR = {
    "command": [["set", "key", "value"], ["get", "key"], ["reset", "target"]],
    "target":  [[], ["'all"], ["key"]],
    "key":     [["'baud"], ["'parity"], ["'stop"], ["'echo"]],
    "value":   [["'9600"], ["'on"], ["'off"], ["'odd"], ["'even"], ["'none"]],
}
# the words 'set', 'get', 'reset' are terminals too:
for word in ("set", "get", "reset"):
    GRAMMAR[word] = [["'" + word]]
