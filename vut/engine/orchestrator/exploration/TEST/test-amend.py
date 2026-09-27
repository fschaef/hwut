#! /usr/bin/env python3
#
# @hwut {
#     title      = "Amending an author's header or conf: one implementation, any language"
#     choices    = ["languages", "replace", "conf", "remove"]
#     tolerance { comment = []  analogy = [] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'exploration/amend.py' -- the text surgery every face that writes
         into an author's file shares ('hwut.config.ignore', 'hwut.renovate',
         the merge's keeping of a tolerance).

    languages   one header per COMMENT STYLE -- never two of one style --
                gains a 'tolerance' scope. The file is printed after, then
                read back by the exploration's own reader: title and
                choices unchanged, the tolerance as meant.
    replace     a header's own multi-line scope replaced by one line; an
                empty one removed, its line with it
    conf        'hwut.conf': a list extended where it stands, a key added
                first, a nested scope found at any depth
    remove      an entry cut from a line it shares, and from a line of
                its own

'comment' and 'analogy' are OFF for this page: the files printed hold
'##' and '((' as data.
______________________________________________________________________________
"""
import sys

from vut.engine.orchestrator.exploration import amend, reader

PAIR_LIST = [("numeric_ratio", "0.047"), ("eq_pattern", '["id=[0-9]+"]')]

#  (style, languages, the header) -- one of each comment style.
LANGUAGE_LIST = (
    ("#",        "sh, Python, Perl, Ruby, R, Make",
     '#!/bin/sh\n# @hwut {\n#     title   = "T"\n#     choices = ["a"]\n# }\necho\n'),
    ("//",       "C++, Java, C#, Go, Rust, JavaScript",
     '// @hwut {\n//     title   = "T"\n//     choices = ["a"]\n// }\nint main() {}\n'),
    ("--",       "SQL, Lua, Haskell, Ada, VHDL",
     '-- @hwut {\n--   title   = "T"\n--   choices = ["a"]\n-- }\nprint(1)\n'),
    (";",        "Lisp, Scheme, NASM, INI",
     '; @hwut {\n;   title   = "T"\n;   choices = ["a"]\n; }\n(print 1)\n'),
    ("%",        "TeX/LaTeX, MATLAB, Erlang, Prolog",
     '% @hwut {\n%   title   = "T"\n%   choices = ["a"]\n% }\n\\documentclass{article}\n'),
    ("'",        "Visual Basic, VBA, VBScript",
     "' @hwut {\n'   title   = \"T\"\n'   choices = [\"a\"]\n' }\nMsgBox 1\n"),
    ("REM",      "BASIC, Windows batch",
     'REM @hwut {\nREM   title   = "T"\nREM   choices = ["a"]\nREM }\necho 1\n'),
    ("!",        "Fortran 90+",
     '! @hwut {\n!   title   = "T"\n!   choices = ["a"]\n! }\nprogram p\n'),
    ('"',        "Vim script",
     '" @hwut {\n"   title   = "T"\n"   choices = ["a"]\n" }\necho 1\n'),
    ("-- |",     "Haskell (Haddock)",
     '-- | @hwut {\n-- |   title   = "T"\n-- |   choices = ["a"]\n-- | }\nmain = pure ()\n'),
    ("/* * */",  "C, CSS, block style with ' * ' lines",
     '/* @hwut {\n *   title   = "T"\n *   choices = ["a"]\n * }\n */\nint x;\n'),
    ("(* *)",    "OCaml, Pascal, Mathematica: opener on the marker's line",
     '(* @hwut {\n     title   = "T"\n     choices = ["a"]\n   } *)\nlet () = ()\n'),
    ("<!-- -->", "XML, HTML, Markdown: opener on the line before",
     '<!--\n@hwut {\n    title   = "T"\n    choices = ["a"]\n}\n-->\n<a/>\n'),
    ("=begin",   "Ruby: a block of words on lines of their own",
     '=begin\n@hwut {\n  title   = "T"\n  choices = ["a"]\n}\n=end\nputs 1\n'),
    ("one line", "any: the header on one line",
     '# @hwut { title = "T"  choices = ["a"] }\necho\n'),
)


def read_back(text):
    """RETURN: str, what the exploration reads: title, choices, and the
               tolerance's numeric ratio and patterns; or the fault."""
    spec, fault_list = reader.read_header(text, "x")
    if spec is None or fault_list:
        return "NOT READ: %s" % (fault_list[0].message if fault_list else "-")
    tolerance = spec.root_parameters.tolerance
    return "title %r, choices %s, numeric_ratio %s, eq_pattern %s" % (
        spec.title, list(spec.choice_db),
        getattr(tolerance, "numeric_ratio", None),
        list(getattr(tolerance, "eq_pattern", None) or []))


def show(text):
    """RETURN: None. The text, framed."""
    for line in text.rstrip("\n").split("\n"): print("    |%s" % line)


def test_languages():
    for style, languages, text in LANGUAGE_LIST:
        print("\n--- %s  (%s)" % (style, languages))
        container = amend.header_container(text)
        if container is None:
            print("    NO HEADER FOUND")
            continue
        after = amend.scope_set(text, container, "tolerance", PAIR_LIST)
        show(after)
        print("    read back: %s" % read_back(after))


def test_replace():
    text = ('# @hwut {\n'
            '#     title   = "T"\n'
            '#     tolerance {\n'
            '#         regions    = false   # about the regions\n'
            '#         eq_pattern = ["x",\n'
            '#                       "y"]\n'
            '#     }\n'
            '#     choices = ["a"]\n'
            '# }\n')
    container = amend.header_container(text)
    scope = amend.scope_list(text, container, "tolerance")[0]
    print("--- the scope's pairs, each value on one line")
    for key, value in amend.scope_pair_list(text, container, scope):
        print("    %s = %s" % (key, value))
    print("--- replaced")
    after = amend.scope_set(text, container, "tolerance", PAIR_LIST)
    show(after)
    print("    read back: %s" % read_back(after))
    print("--- emptied: the scope goes, its line with it")
    after = amend.scope_set(text, container, "tolerance", [])
    show(after)
    print("    read back: %s" % read_back(after))


def test_conf():
    text = ('hwut {\n'
            '    ignore = ["a.py"]   # helpers\n'
            '    app_defaults {\n'
            '        tolerance { numeric_ratio = 0.1 }\n'
            '    }\n'
            '    apps {\n'
            '        gen.c { tolerance { whitespace = false } }\n'
            '    }\n'
            '}\n')
    container = amend.conf_container(text)
    print("--- the list extended where it stands; a name it holds not twice")
    show(amend.list_extend(text, container, "ignore", ["b.py", "a.py"]))
    print("--- a key added as the first entry")
    show(amend.entry_add(text, container, 'title = "T"', first_f=True))
    print("--- every 'tolerance' at any depth")
    for scope in amend.scope_list(text, container, "tolerance"):
        print("    %s" % text[scope.i_key:scope.i_end])
    print("--- a conf without the list gains it first")
    bare = 'hwut {\n    title = "T"\n}\n'
    show(amend.list_extend(bare, amend.conf_container(bare), "ignore", ["x.py"]))


def test_remove():
    text = '# @hwut { title = "A"  numeric = 0.01  whitespace_eqv = yes }\n'
    container = amend.header_container(text)
    entry = [e for e in amend.entry_list(text, container.i_open,
                                         container.i_close,
                                         container.decoration)
             if e.key == "numeric"][0]
    print("--- from a shared line")
    show(amend.entry_remove(text, container, entry))
    text = 'hwut {\n    on_entry  = "true"\n    slash_eqv = false\n}\n'
    container = amend.conf_container(text)
    entry = [e for e in amend.entry_list(text, container.i_open,
                                         container.i_close)
             if e.key == "slash_eqv"][0]
    print("--- from a line of its own: the line goes")
    show(amend.entry_remove(text, container, entry))


CHOICE_DB = {"languages": test_languages, "replace": test_replace,
             "conf": test_conf, "remove": test_remove}

choice = sys.argv[1] if len(sys.argv) > 1 else "languages"
CHOICE_DB[choice]()

#  THE STREAM COMPLETED (R-70).
print("<hwut-end>")
