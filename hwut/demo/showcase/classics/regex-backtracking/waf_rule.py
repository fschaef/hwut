r"""waf_rule.py -- the decisive tail of the WAF rule of 2 July 2019, and its
linear equivalent. The rule as deployed (Cloudflare's post-mortem, 12 July
2019) was

  (?:(?:\"|'|\]|\}|\\|\d|(?:nan|infinity|true|false|null|undefined|symbol|math)|\`|\-|\+)+[)]*;?((?:\s|-|~|!|{}|\|\||\+)*.*(?:.*=.*)))

and the post-mortem singles out its end, '.*(?:.*=.*)', as the part that
backtracks: two greedy '.*' in a row before a literal that never comes make
a backtracking engine try every way of splitting the input between them,
at every start position.

As a TEST -- does the input match or not -- the tail means 'there is an
"="'. A single literal says the same thing, and any engine finds it in one
pass.
"""
import re

RULE_DB = {
    "deployed-2019": r".*(?:.*=.*)",     # the tail of the rule as deployed
    "linear":        r"=",                # the same yes/no, one pass
}


def compiled(name):
    return re.compile(RULE_DB[name])
