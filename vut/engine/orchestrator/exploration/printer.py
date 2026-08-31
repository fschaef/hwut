"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Print a resolved configuration IN THE SPECIFICATION LANGUAGE. What
         is printed can be read back: the shape an author writes is the
         shape he is shown.

    test-a.py {
        title = "Tolerances"
        choices {
            two {
                caps {
                    timeout_sec = 30.0            # app
                    network     = true            # default
                }
                numeric = 0.05
                comment = "//"                    # hwut.conf:3
            }
        }
    }

The PROVENANCE stands in a HOCON comment, and only where the value is not
this choice's own word (see provenance.py).

    no_default_f    drops every line that carries 'default': what
                    remains is what somebody stated.
    provenance_f    every stated value names its place -- the file and
                    the line it stands on -- rather than the short word.
    gnu_f           the place in the GNU error format, at the LINE'S
                    BEGINNING where an editor's error parser looks for
                    it:

                        test-a.py:5:23:     numeric = 0.05
                        hwut.conf:3:21:     slash_eqv = false
                                            title = "T"

                    EVERY line carries a place. A line with none of
                    its own -- a brace, a title, a defaulted value --
                    INHERITS the place of what encloses it, so a walk
                    through the quickfix list never lands nowhere.

                    The places are one column, padded to the longest of
                    them.
______________________________________________________________________________
"""
from .relation      import RELATION, default_of
from .configuration_tree import KEY_TO_FIELD

_INDENT      = "    "
_VALUE_COLUMN = 46


def app_text(app, no_default_f=False, provenance_f=False, gnu_f=False):
    """
    RETURN: str, the whole test application in the specification
            language: its title and every choice, with every parameter
            the framework will use.

    'no_default_f' drops the values nobody stated -- the noise an author
    already knows -- leaving what somebody chose. 'provenance_f' names
    the place of every stated value; 'gnu_f' names it in the GNU error
    format.
    """
    #  THE APPLICATION'S OWN PLACE: what every line of it inherits that
    #  has none nearer to hand.
    app_place = _gnu_place(app.source_file, app.position) if gnu_f else None

    pair_list = [(app_place, "%s {" % app.source_file),
                 _line("title", app.title, None, 1, provenance_f, gnu_f)]
    if app.language is not None:
        place, text = _line("language", app.language, None, 1,
                            provenance_f, gnu_f)
        #  NEVER SILENT (R-73): a language the extension selected is
        #  said to be, whatever the flags -- the author did not write it.
        if getattr(app, "language_derived_f", False):
            text = "%s# derived: extension -> 'language-setup'" \
                   % text.ljust(_VALUE_COLUMN)
        pair_list.append((place, text))

    pair_list.append((app_place, "%schoices {" % _INDENT))
    for choice in sorted(app.choice_db, key=lambda c: (c is None, c or "")):
        pair_list.append((app_place, "%s%s {" % (_INDENT * 2,
                                                 "-" if choice is None
                                                 else choice)))
        pair_list.extend(_parameter_line_list(
            app.choice_db[choice],
            (app.origin_db or {}).get(choice, {}), 3, no_default_f,
            provenance_f, gnu_f, app_place))
        pair_list.append((app_place, "%s}" % (_INDENT * 2)))
    pair_list.append((app_place, "%s}" % _INDENT))
    pair_list.append((app_place, "}"))
    return _joined(_inherited(pair_list, app_place))


def case_text(case, origin_db=None, no_default_f=False,
              provenance_f=False, gnu_f=False):
    """
    RETURN: str, one test case in the specification language -- the same
            shape as 'app_text', for a single choice.
    """
    head = "%s %s {" % (case.source_file,
                        "-" if case.choice is None else case.choice)
    if case.misdep_f: head += "   # [MISDEP]"
    case_place = _gnu_place(case.source_file, case.position) if gnu_f \
                 else None
    return _joined(_inherited([(case_place, head)]
                   + _parameter_line_list(case.parameters,
                                          origin_db or {}, 1,
                                          no_default_f, provenance_f,
                                          gnu_f, case_place)
                   + [(case_place, "}")], case_place))


def _parameter_line_list(parameters, origin_db, depth, no_default_f,
                         provenance_f=False, gnu_f=False,
                         enclosing_place=None):
    """
    YIELD is a list here: [0] str | None  the line's PLACE, in the GNU
                                          error format, where it has one
                          [1] str         the line itself

    One pair per parameter the framework will use, scopes written as
    scopes.

    A scope whose every leaf would be dropped is dropped whole: an empty
    brace pair says nothing.
    """
    result = []
    for key in KEY_TO_FIELD:
        field     = KEY_TO_FIELD[key]
        value     = getattr(parameters, field)
        leaf_list = [name for name in RELATION
                     if name.startswith("%s." % key)]

        if not leaf_list:
            origin = origin_db.get(key)
            if no_default_f and _default_f(origin): continue
            result.append(_line(key, _effective(key, value), origin, depth,
                                provenance_f, gnu_f))
            continue

        inner_list = []
        for name in leaf_list:
            member = name.split(".", 1)[1]
            leaf   = getattr(value, member) if value is not None else None
            origin = origin_db.get(name)
            if no_default_f and _default_f(origin): continue
            inner_list.append(_line(member,
                                    leaf if leaf is not None
                                         else default_of(name),
                                    origin, depth + 1,
                                    provenance_f, gnu_f))
        if not inner_list: continue
        #  A SCOPE'S BRACES take the place of the first thing STATED
        #  inside them; where nothing is, the enclosing place.
        scope_place = next((place for place, _ in inner_list if place),
                           enclosing_place)
        result.append((scope_place, "%s%s {" % (_INDENT * depth, key)))
        result.extend(inner_list)
        result.append((scope_place, "%s}" % (_INDENT * depth)))
    return result


def _gnu_place(file, position):
    """
    RETURN: str, 'file:line:column:' -- one place in the GNU error
            format.
            None, there is no position to name.
    """
    if position is None: return None
    return "%s:%d:%d:" % (file, position.line, position.column)


def _inherited(pair_list, enclosing_place):
    """
    RETURN: list, the pairs with every empty place filled from the
            ENCLOSING one.

    A line with no place of its own -- a defaulted value, a brace --
    would otherwise be an entry in an editor's error list that jumps
    nowhere. It takes the place of what ENCLOSES it, not of the line
    above it: a default stands in no relation to whatever value happens
    to precede it.
    """
    return [(place or enclosing_place, text) for place, text in pair_list]


def _joined(pair_list):
    """
    RETURN: str, the lines. Where any line carries a PLACE, the places
            stand in a column of their own at the beginning, padded to
            the longest of them; a line without one keeps the column
            empty.
    """
    width = max((len(place) for place, _ in pair_list if place),
                default=0)
    if not width:
        return "\n".join(text for _, text in pair_list)
    return "\n".join("%s%s" % ((place or "").ljust(width + 1), text)
                      for place, text in pair_list)


def _effective(key, value):
    """RETURN: the value that will be used: the stated one, or the value
    the owning component declares."""
    return default_of(key) if value is None else value


def _default_f(origin):
    """RETURN: bool, nobody stated this value; the owner declared it."""
    return origin is None or str(origin) == "default"


def _line(name, value, origin, depth, provenance_f=False, gnu_f=False):
    """
    RETURN: [0] str | None, the line's PLACE where '--gnu' asks for one:
                'file:line:column:', which is where an editor's error
                parser looks -- at the BEGINNING.
            [1] str, the line in the specification language, carrying the
                provenance in a comment where that is where it belongs.

    Without a flag, a value the author wrote HERE carries no comment: he
    is reading his own file.
    """
    text = "%s%s = %s" % (_INDENT * depth, name, _printed(value))
    if origin is None: return (None, text)

    if gnu_f:
        place = origin.gnu_text()
        return ("%s:" % place if origin.file else None, text)

    comment = _place_text(origin) if provenance_f else str(origin)
    if not comment: return (None, text)
    return (None, "%s# %s" % (text.ljust(_VALUE_COLUMN), comment))


def _place_text(origin):
    """RETURN: str, 'file:line' where the value has a place, the short
    word where it has none."""
    if origin.file is None:  return origin.text
    if origin.line is None:  return origin.file
    return "%s:%d" % (origin.file, origin.line)


def _printed(value):
    """RETURN: str, a value as a specification writes it -- strings in
    double quotes, booleans lower case, absence as 'null'."""
    match value:
        case None:   return "null"
        case True:   return "true"
        case False:  return "false"
        case str():  return '"%s"' % value
        case tuple():
            return "[%s]" % ", ".join(_printed(item) for item in value)
        case _:      return repr(value)
