"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Say where each value came from, while the sources still stand
         apart -- once they are folded, the answer is unrecoverable.

The provenances, in the order they overrule one another:

    None              the choice's own word: the author wrote it here
    "app"             the application's root, reaching every choice
    "hwut.conf:<n>"   'app_defaults' of the directory, or the 'apps' entry
                      that carries this application; the line is the key's
    "--hwut-info"     the application said it through its info block
    "default"         the component that owns the parameter declared it

The names are the relation table's, so a scope's leaf reads
'caps.timeout_sec' and a plain parameter reads 'numeric'.
______________________________________________________________________________
"""
import os
from dataclasses    import dataclass

from .relation      import RELATION
from .configuration_tree import KEY_TO_FIELD, E_Origin


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where one value came from, said two ways.

    'text' is what a reader wants beside the value -- 'app', 'default',
    'hwut.conf:3'. 'file' and 'line' are the place itself, for the
    services that print places ('--provenance', '--gnu'); they are 'None'
    where there is no place, which is what a declared default has.
    """
    text: str
    file: str | None = None
    line: int | None = None
    column: int | None = None

    def __str__(self):
        """RETURN: str, the short form -- what stands in a comment."""
        return self.text

    def gnu_text(self):
        """
        RETURN: str, the place in the GNU error format,
                'file:line:column'; the short form where there is no
                place.
        """
        if self.file is None: return self.text
        if self.column is None: return "%s:%d" % (self.file, self.line)
        return "%s:%d:%d" % (self.file, self.line, self.column)


def of_choice(spec, choice, app_defaults, directory_spec):
    """
    RETURN: dict, parameter name -> Provenance, for one choice of one
            specification.
    """
    result             = {}
    choice_parameters  = spec.choice_db[choice]
    choice_position_db = (spec.choice_position_db or {}).get(choice, {})
    root_position_db   = spec.position_db or {}
    conf_position_db   = getattr(directory_spec, "app_defaults_position_db",
                                 None) or {}
    conf_file_db       = getattr(directory_spec, "app_defaults_file_db",
                                 None) or {}

    #  An application whose carrier is 'hwut.conf' or the interview has
    #  ONE provenance for everything it states: the carrier that spoke.
    carrier = None
    if   spec.origin is E_Origin.INTERVIEW: carrier = "--hwut-info"
    elif spec.origin is E_Origin.CONF:      carrier = "hwut.conf"

    conf_file = "hwut.conf"
    for name in _name_list():
        if _stated_f(choice_parameters, name):
            result[name] = _made(carrier, None, spec.source_file,
                                 choice_position_db, name, conf_file)
        elif _stated_f(spec.root_parameters, name):
            result[name] = _made(carrier, "app", spec.source_file,
                                 root_position_db, name, conf_file)
        elif app_defaults is not None and _stated_f(app_defaults, name):
            stated_in = conf_file_db.get(name) \
                        or conf_file_db.get(name.split(".")[0]) or conf_file
            result[name] = _made(stated_in, None, stated_in,
                                 conf_position_db, name, stated_in)
        else:
            result[name] = Provenance("default")
    return result


def _made(carrier, own_text, file, position_db, name, conf_file):
    """
    RETURN: Provenance, the text a reader wants and the place itself.

    'own_text' is what a value stated by the file ITSELF reads as --
    'app' for the application's root, nothing at all for the choice's own
    word. A carrier speaks in its own name instead.
    """
    position = position_db.get(name) or position_db.get(name.split(".")[0])
    if carrier == "--hwut-info":
        return Provenance("--hwut-info", file)
    if (carrier is not None and carrier.endswith(".conf")) \
       or carrier is None and file == conf_file:
        #  THE CONF THAT SPOKE, by the name it has in the tree: the
        #  root's is 'hwut-root.conf', a directory's 'hwut.conf'; one
        #  met on the climb is named by its file name, never by an
        #  absolute path.
        label = os.path.basename(conf_file) if os.path.isabs(conf_file) \
                else conf_file
        text = ("%s:%d" % (label, position.line)) if position else label
        return Provenance(text, conf_file,
                          position.line if position else None,
                          position.column if position else None)
    return Provenance(own_text or "", file,
                      position.line if position else None,
                      position.column if position else None)


def _name_list():
    """
    YIELD: [0] str  one parameter name: a scope's leaf as
                    'caps.timeout_sec', a plain parameter as 'numeric'.
    """
    for key in KEY_TO_FIELD:
        leaf_list = [name for name in RELATION
                     if name.startswith("%s." % key)]
        if leaf_list: yield from leaf_list
        else:         yield key


def _stated_f(parameters, name):
    """RETURN: bool, this record states a value for 'name'."""
    if parameters is None: return False
    if "." in name:
        key, member = name.split(".", 1)
        scope       = getattr(parameters, KEY_TO_FIELD[key])
        return scope is not None and getattr(scope, member) is not None
    return getattr(parameters, KEY_TO_FIELD[name]) is not None


