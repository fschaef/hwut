#! /usr/bin/env python3
"""app_argv.py -- the same test application with a hand-written front end,
as most test applications start: a dictionary and sys.argv[1]."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numfmt


def table(locale):
    numfmt.configure(locale)
    for x in (0, 7.5, 1234.5, 1234567.891):
        print("%-6s %14s" % (locale, numfmt.fmt(x)))


CHOICE_DB = {"de": lambda: table("de"), "en": lambda: table("en"), "ch": lambda: table("ch")}

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    CHOICE_DB[choice]()
    print("<hwut-end>")
