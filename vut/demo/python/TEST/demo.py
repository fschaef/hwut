#! /usr/bin/env python3
#
# @hwut {
#     title   = "Demo: what hwut tolerates, and where it is said"
#     choices {
#         plain       { }
#         tolerance   { tolerance {
#                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
#                           numeric_ratio = 0.01
#                       } }
#         constraints { tolerance {
#                           constraints = ["load >= 0 and load <= 100",
#                                          "even % 2 == 0",
#                                          "twice == 2 * once"]
#                       } }
#         analogies   { }
#     }
# }
#
"""
______________________________________________________________________________
A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.

    hwut.run                   runs every choice below, compares with GOOD/
    hwut.accept demo.py        records what the choices print as GOOD
    hwut.accept.interactive    shows OUTPUT against GOOD, key by key
    hwut.config.show demo.py   prints what hwut READ from the header above

The header above is the whole configuration: a title, and one scope per
choice. hwut calls 'demo.py <choice>' and compares what it prints on stdout
with 'GOOD/demo.py--<choice>.txt'. '<hwut-end>' closes the stream: a stream
without it never COMPLETED and is not accepted.

Every run is seeded by the clock, so the output differs from run to run --
and every choice passes anyway. Each shows WHY:

plain        nothing varies; nothing is tolerated. The output must equal
             GOOD, line by line.

tolerance    'eq_pattern': a greeting drawn at random; any greeting the
             pattern names is EQUIVALENT to any other.
             'numeric_ratio': a value drawn from [19.91, 20.09]. The band
             belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
             20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
             from the interval passes; 20.30 would not.

constraints  '((name: value))' BINDS a value; the expressions under
             'constraints' judge it, not the GOOD's value. 'load' may be
             anything from 0 to 100; 'even' any even number; 'twice' must be
             twice 'once', whatever 'once' is. A law over two variables is
             checked once both are bound. A binding that breaks its law is
             red.

analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
             is equivalent where the mapping holds throughout the stream --
             the same handle opened, read and closed. A handle that changes
             in mid-stream is red.
______________________________________________________________________________
"""
import random
import sys
import time

GREETING_TUPLE = ("hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj")


def plain():
    """RETURN: None. Prints what never varies."""
    print("the first line")
    print("the second line: 1 2 3")


def tolerance():
    """RETURN: None. Prints a greeting and a value, both drawn at random."""
    print("greeting: %s, world" % random.choice(GREETING_TUPLE))
    print("value:    %.2f" % random.uniform(19.91, 20.09))


def constraints():
    """RETURN: None. Prints bindings, each drawn at random, each lawful."""
    print("load  ((load: %.1f)) %%" % random.uniform(0.0, 100.0))
    print("even  ((even: %i))" % (2 * random.randint(0, 500)))
    once = random.randint(1, 50)
    print("once  ((once: %i))" % once)
    print("twice ((twice: %i))" % (2 * once))


def analogies():
    """RETURN: None. Prints two handles, each drawn at random, each used
    consistently from opening to closing."""
    first, second = random.sample(range(0x1000, 0x10000), 2)
    print("open  ((%04x)) input.txt" % first)
    print("open  ((%04x)) output.txt" % second)
    print("read  ((%04x)) 17 lines" % first)
    print("write ((%04x)) 17 lines" % second)
    print("close ((%04x))" % first)
    print("close ((%04x))" % second)


CHOICE_DB = {"plain":       plain,
             "tolerance":   tolerance,
             "constraints": constraints,
             "analogies":   analogies}

random.seed(time.time_ns())
choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
CHOICE_DB[choice]()
print("<hwut-end>")
