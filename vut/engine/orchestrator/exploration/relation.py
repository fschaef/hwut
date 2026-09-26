"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: One table relating HWUT's parameter names to the configuration
         members that carry them. It serves BOTH directions:

    write    the parsed values into a component's configuration
    read     the default a component DECLARES for a member

    RELATION = {
        "tolerance.numeric_ratio":  (ConfigCompare, "numeric_tolerance_ratio"),
        "analogy":  (ConfigCompare, ("analogy_f", "analogy_begin_marker",
                                     "analogy_end_marker"), ANALOGY),
    }

A plain entry names ONE member. An ADAPTED entry names several, and the
adapter carries the two tiny functions that bridge the shapes:

    forward     our value      -> {member: value, ...}
    backward    {member: ...}  -> our value

Backward is what makes a DEFAULT derivable: compare declares 'analogy_f',
'analogy_begin_marker' and 'analogy_end_marker'; backward reads those three
declarations and hands back the marker PAIR our vocabulary speaks in. So no
default is restated here, and no component is asked to keep a second face in
step with its own.

A configuration is a frozen dataclass, so its default stands in its
declaration and 'dataclasses.fields()' reads it without constructing
anything. A component takes part by declaring its configuration, and by
nothing else.

NO PARAMETER IS 'None' AS AN END RESULT. Where a component declares 'None',
'None' IS the value: it documents that the thing is absent. The RECORD keeps
its own 'None's for a different reason: the store must know what was CHOSEN.

The table is checked AT IMPORT against the classes it names.
______________________________________________________________________________
"""
from dataclasses import dataclass, fields, replace, MISSING

from ...procsitter.api             import ProcsitterConfig
from ...compare.api                import ConfigurationDiffDisplayParameters
from ...bookkeeper.api             import CAPS_FIELD_DB
from .owner_faces_provisional import (ConfigBuild, ConfigCaps,
                                      ConfigCanonicalise, ConfigCompare,
                                      ConfigRunner, ConfigStore)


@dataclass(frozen=True)
class Adapter:
    """The two functions that bridge one word of ours and several members
    of a component's own configuration."""
    forward:  object          # our value      -> {member: value, ...}
    backward: object          # {member: ...}  -> our value


def _analogy_forward(pair):
    """RETURN: dict, the members that say what a marker pair says. The
    EMPTY pair switches analogies off and leaves the markers alone."""
    if not pair: return {"analogy_f": False}
    return {"analogy_f":            True,
            "analogy_begin_marker": pair[0],
            "analogy_end_marker":   pair[1]}


def _analogy_backward(member_db):
    """RETURN: tuple, the marker pair the members describe; '()' where
    analogies are off."""
    if not member_db["analogy_f"]: return ()
    return (member_db["analogy_begin_marker"],
            member_db["analogy_end_marker"])


def _constraints_forward(expression_list):
    """RETURN: dict, the members that say what an expression list says.

    The DATABASE is compare's to build ('constraint_db' relates a variable
    to the expressions that mention it, R-55); this side states only that
    constraints are in force and hands the expressions over as written.
    """
    return {"constraint_f":  bool(expression_list),
            "constraint_db": tuple(expression_list)}


def _constraints_backward(member_db):
    """RETURN: tuple, the expressions; '()' where constraints are off."""
    if not member_db["constraint_f"]: return ()
    return tuple(member_db["constraint_db"] or ())


def _comment_forward(pair):
    """RETURN: dict, the members that say what a marker pair says. The
    EMPTY pair switches ignored lines off and leaves the markers
    alone."""
    if not pair: return {"ignored_line_f": False}
    return {"ignored_line_f":            True,
            "ignored_line_begin_marker": pair[0],
            "ignored_line_end_marker":   pair[1]}


def _comment_backward(member_db):
    """RETURN: tuple, the marker pair of an ignored line; '()' where
    ignored lines are off."""
    if not member_db["ignored_line_f"]: return ()
    return (member_db["ignored_line_begin_marker"],
            member_db["ignored_line_end_marker"])


ANALOGY     = Adapter(_analogy_forward,     _analogy_backward)
CONSTRAINTS = Adapter(_constraints_forward, _constraints_backward)
COMMENT     = Adapter(_comment_forward,     _comment_backward)


#  HWUT's word -> (class, member) or (class, (member, ...), adapter).
#  A SCOPE of ours ('caps', 'build') relates leaf by leaf: the scope is
#  our grammar, the members are the owner's.
RELATION = {
    "build.framework":           (ConfigBuild, "framework"),
    "build.executable":          (ConfigBuild, "executable"),

    #  THE SUPERVISOR'S OWN DOOR ANSWERS FOR WHAT IT ENFORCES (R-78):
    #  the default 'hwut.config.show' prints is the default the kill obeys,
    #  and the mapping is 'CAPS_FIELD_DB', the tree's one word for it.
    "caps.timeout_sec":          (ProcsitterConfig, CAPS_FIELD_DB["timeout_sec"]),
    "caps.cpu_sec":              (ProcsitterConfig, CAPS_FIELD_DB["cpu_sec"]),
    "caps.memory_mb":            (ProcsitterConfig, CAPS_FIELD_DB["memory_mb"]),
    "caps.file_size_mb":         (ProcsitterConfig, CAPS_FIELD_DB["file_size_mb"]),
    "caps.child_process_max_n":  (ProcsitterConfig, CAPS_FIELD_DB["child_process_max_n"]),
    "caps.file_handle_max_n":    (ConfigCaps, "file_handle_max_n"),
    "caps.network":              (ConfigCaps, "network"),
    "caps.write_directory_list": (ConfigCaps, "write_directory_list"),

    "pype":            (ConfigCanonicalise, "pype"),

    #  EVERY LEXICAL TOLERANCE IS ONE SCOPE (E-42): there is no second
    #  place a tolerance may be written, and 'hwut.config.show' prints them
    #  inside the braces because the printer walks THESE keys.
    "tolerance.numeric_ratio": (ConfigCompare, "numeric_tolerance_ratio"),
    "tolerance.slash":         (ConfigCompare, "backslash_f"),
    "tolerance.whitespace":    (ConfigCompare, "whitespace_f"),
    "tolerance.eq_pattern":    (ConfigCompare, "equivalent_pattern_list"),
    "tolerance.nothing":       (ConfigCompare,
                                "visible_nothing_pattern_list"),
    "tolerance.analogy":       (ConfigCompare, ("analogy_f",
                                                "analogy_begin_marker",
                                                "analogy_end_marker"),
                                               ANALOGY),
    "tolerance.constraints":   (ConfigCompare, ("constraint_f",
                                                "constraint_db"),
                                               CONSTRAINTS),
    "tolerance.comment":       (ConfigCompare, ("ignored_line_f",
                                                "ignored_line_begin_marker",
                                                "ignored_line_end_marker"),
                                               COMMENT),
    #  REGION FRAMING, SWITCHABLE LIKE EVERY OTHER LEXICAL FEATURE
    #  (C-4). 'tolerance.regions = false': '##!' and '####' are
    #  ordinary content -- what a text that TALKS ABOUT framing needs.
    "tolerance.regions":       (ConfigCompare, "regions_f"),

    #  THE LINE LEVEL'S NUMBERS (compare C-16), answered by compare's OWN
    #  declaration -- no mirror to keep in step.
    "diff_display_parameters.search_budget":  (ConfigurationDiffDisplayParameters, "search_budget"),
    "diff_display_parameters.margin":         (ConfigurationDiffDisplayParameters, "margin"),
    "diff_display_parameters.lowest_n":       (ConfigurationDiffDisplayParameters, "lowest_n"),
    "diff_display_parameters.context_k":      (ConfigurationDiffDisplayParameters, "context_k"),

    "same":            (ConfigStore,  "same_nominal_f"),
    "interactive":     (ConfigRunner, "interactive_f"),
    "execute":         (ConfigRunner, "execute"),
    "output":          (ConfigRunner, "output"),
}


def _member_list(entry):
    """RETURN: list[str], the members one entry names -- one for a plain
    entry, several for an adapted one."""
    member = entry[1]
    return [member] if isinstance(member, str) else list(member)


def _assert_relation():
    """RETURN: None. Checked at IMPORT: every related member exists on
    its class and declares a default.

    A member renamed or a default forgotten in a component fails HERE, at
    the import of this module, naming the parameter, the class and the
    member -- not at the first case that happens to need it.

    Raised, not 'assert'ed: the check must stand under 'python -O'.
    """
    complaint_list = []
    for name in sorted(RELATION):
        entry    = RELATION[name]
        cls      = entry[0]
        field_db = {f.name: f for f in fields(cls)}
        for member in _member_list(entry):
            if member not in field_db:
                complaint_list.append("'%s': %s has no member '%s'"
                                      % (name, cls.__name__, member))
                continue
            f = field_db[member]
            if f.default is MISSING and f.default_factory is MISSING:
                complaint_list.append("'%s': %s.%s declares no default"
                                      % (name, cls.__name__, member))
    if complaint_list:
        raise ImportError(
            "relation table and configuration classes disagree:\n    %s"
            % "\n    ".join(complaint_list))


_assert_relation()


def default_of(name):
    """
    RETURN: the value the owning component DECLARES for parameter 'name'
            -- what fills the blank where the author stated nothing.

    For an adapted entry the declarations of every member it names are
    read and handed to the adapter's 'backward', so the default is
    DERIVED from the component's own declaration and restated nowhere.

    A declared 'None' IS the value: it says the thing is absent -- no
    build framework, no canonicalisation. Nothing replaces it.

    Raises KeyError for a name the table does not carry: an unknown
    parameter is refused at the door, not defaulted.
    """
    entry = RELATION[name]
    cls   = entry[0]
    if len(entry) == 2:
        return _declared(cls, entry[1], name)
    member_db = {member: _declared(cls, member, name)
                 for member in _member_list(entry)}
    return entry[2].backward(member_db)


def configuration_of(cls, value_db):
    """
    RETURN: an instance of 'cls', every member this table relates to it
            set from 'value_db' where a value stands there, at the
            component's declared default where none does.

    'value_db' maps HWUT's parameter names to values; 'None' means the
    author stated nothing. What comes back is COMPLETE.
    """
    change_db = {}
    for name, entry in RELATION.items():
        if entry[0] is not cls:            continue
        value = value_db.get(name)
        if value is None:                  continue
        if len(entry) == 2: change_db[entry[1]] = value
        else:               change_db.update(entry[2].forward(value))
    return replace(cls(), **change_db)


def value_db_of(parameters):
    """
    RETURN: dict, HWUT parameter name -> the value the record states,
            'None' where it states nothing.

    The scopes of the record ('caps', 'build') are flattened onto the
    dotted names this table carries. The record itself is untouched: its
    'None's are what the store records.
    """
    from .configuration_tree import KEY_TO_FIELD
    result = {}
    for name in RELATION:
        if "." in name:
            scope_name, member = name.split(".", 1)
            scope = getattr(parameters, scope_name)
            result[name] = getattr(scope, member) if scope else None
        else:
            result[name] = getattr(parameters, KEY_TO_FIELD[name])
    return result


def effective(parameters, name):
    """
    RETURN: the EFFECTIVE value of parameter 'name': the record's where
            the author stated one, the owner's declared default else.
    """
    value = value_db_of(parameters)[name]
    return default_of(name) if value is None else value


def _declared(cls, member, name):
    """
    RETURN: the default 'cls' declares for 'member', the factory called
            where the default is a factory.

    Raises KeyError where nothing is declared, naming what is silent.
    """
    field_db = {f.name: f for f in fields(cls)}
    if member not in field_db:
        raise KeyError("'%s': %s has no member '%s'"
                       % (name, cls.__name__, member))
    f = field_db[member]
    if f.default is not MISSING:         return f.default
    if f.default_factory is not MISSING: return f.default_factory()
    raise KeyError("'%s': %s.%s declares no default"
                   % (name, cls.__name__, member))
