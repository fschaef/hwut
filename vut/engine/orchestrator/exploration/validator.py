"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Turn the annotated tree into the plain tree, or refuse by name,
         with a position. The validator is the ONLY consumer of the
         annotated tree; on acceptance nothing downstream knows it existed.

Two vocabularies, one per carrier (README 6):

    HEADER      'title' (required), 'language', 'choices', and every test
                parameter -- at the root as defaults and inside choices.

    hwut.conf   directory keys at the root; 'language-setup' holding only
                language names; 'apps' holding only file names, each entry
                the header vocabulary entire and unchanged.

Every fault accumulates; validation completes.
______________________________________________________________________________
"""
from .fault         import Fault, E_FaultKind
from vut.language_support.python.hwut_hocon import (ScalarNode,
                                                      ListNode,
                                                      ObjectNode)
from .specification import (TestParameters, TestAppSpec, DirectorySpec,
                            LanguageSetup, Build, Caps, Target, E_Origin,
                            KEY_TO_FIELD, ROOT_ONLY_KEY_SET)

_STRUCTURAL_KEY_SET = ("title", "language", "choices")

#  The caps that are a positive quantity, and the type each carries.
_CAP_POSITIVE_SET   = {"timeout_sec":         float,
                       "cpu_sec":             float,
                       "memory_mb":           int,
                       "file_size_mb":        int,
                       "child_process_max_n": int,
                       "file_handle_max_n":   int}
_CONF_KEY_SET       = ("on_entry", "on_exit", "ignore", "collision",
                       "dependency", "default_app", "language-setup",
                       "apps")


def validate_header(hwut_node, file, origin=E_Origin.HEADER,
                    source_file=None):
    """
    RETURN: [0] TestAppSpec | None, the specification; None if nothing
                usable stands here.
            [1] list[Fault], every fault found.

    'hwut_node' is the annotated object behind the 'hwut' key. 'file'
    names the CARRIER for faults; 'source_file' the test application --
    they differ for an 'apps' entry, whose carrier is 'hwut.conf'.
    """
    if source_file is None: source_file = file
    fault_list  = []
    parameters  = {}
    position_db = {}
    title       = None
    language    = None
    choice_db   = {}
    choice_position_db = {}
    choices_f   = False

    for entry in hwut_node.entry_list:
        if entry.key == "title":
            title = _string(entry, file, fault_list)
        elif entry.key == "language":
            language = _string(entry, file, fault_list)
        elif entry.key == "choices":
            choices_f = True
            choice_db = _choices(entry, file, fault_list,
                                 choice_position_db)
        elif entry.key in KEY_TO_FIELD:
            _parameter(entry, parameters, file, fault_list, position_db)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s'" % entry.key))

    if title is None:
        fault_list.append(Fault(
            E_FaultKind.VOCABULARY, file, hwut_node.position,
            "'title' is required and absent"))
        return None, fault_list

    root = TestParameters(**parameters)
    if not choices_f:
        choice_db = {None: TestParameters()}

    return TestAppSpec(source_file        = source_file,
                       title              = title,
                       language           = language,
                       root_parameters    = root,
                       choice_db          = choice_db,
                       origin             = origin,
                       position           = hwut_node.position,
                       position_db        = position_db,
                       choice_position_db = choice_position_db), fault_list


def validate_conf(hwut_node, file):
    """
    RETURN: [0] DirectorySpec, the directory's own keys.
            [1] dict, source file name -> TestAppSpec (origin CONF) --
                the 'apps' entries.
            [2] list[Fault], every fault found.
    """
    fault_list     = []
    field_db       = {}
    language_setup = {}
    app_db         = {}

    for entry in hwut_node.entry_list:
        if entry.key in ("on_entry", "on_exit"):
            value = _string(entry, file, fault_list)
            if value is not None: field_db[entry.key] = value
        elif entry.key == "ignore":
            value = _string_list(entry, file, fault_list)
            if value is not None: field_db["ignore"] = value
        elif entry.key == "collision":
            value = _target_list(entry, file, fault_list)
            if value is not None: field_db["collision"] = value
        elif entry.key == "dependency":
            value = _dependency(entry, file, fault_list)
            if value is not None: field_db["dependency"] = value
        elif entry.key == "default_app":
            parameters, position_db = _default_app(entry, file, fault_list)
            field_db["default_app"]             = parameters
            field_db["default_app_position_db"] = position_db
        elif entry.key == "language-setup":
            language_setup = _language_setup(entry, file, fault_list)
        elif entry.key == "apps":
            app_db = _apps(entry, file, fault_list)
        elif entry.key in KEY_TO_FIELD or entry.key in _STRUCTURAL_KEY_SET:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "'%s' at the root of hwut.conf: the root carries "
                "directory keys only; this key belongs to an 'apps' "
                "entry" % entry.key))
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s'" % entry.key))

    field_db.setdefault("dependency", {})
    spec = DirectorySpec(language_setup = language_setup,
                         position       = hwut_node.position,
                         **field_db)
    return spec, app_db, fault_list


def document_hwut_node(document, file, fault_list):
    """
    RETURN: ObjectNode, the object behind the document's 'hwut' key.
            None, no such key (fault recorded).
    """
    entry = document.get("hwut")
    if entry is None or not isinstance(entry.node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.VOCABULARY, file, document.position,
            "no 'hwut { ... }' block"))
        return None
    for other in document.entry_list:
        if other.key != "hwut":
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, other.key_position,
                "'%s' outside the 'hwut' block" % other.key))
    return entry.node


def _choices(entry, file, fault_list, choice_position_db=None):
    """
    RETURN: dict, choice name -> TestParameters -- from the map form or
            the list form; empty on a fault.
    """
    if isinstance(entry.node, ListNode):
        result = {}
        for item in entry.node.item_list:
            if not isinstance(item, ScalarNode) \
               or not isinstance(item.value, str):
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, item.position,
                    "the list form of 'choices' carries names only"))
                continue
            result[item.value] = TestParameters()
        return result

    if isinstance(entry.node, ObjectNode):
        result = {}
        for choice in entry.node.entry_list:
            if not isinstance(choice.node, ObjectNode):
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, choice.key_position,
                    "choice '%s' must carry an object" % choice.key))
                continue
            parameters  = {}
            position_db = {}
            if choice_position_db is not None:
                choice_position_db[choice.key] = position_db
            for inner in choice.node.entry_list:
                if inner.key in ROOT_ONLY_KEY_SET:
                    fault_list.append(Fault(
                        E_FaultKind.VOCABULARY, file, inner.key_position,
                        "'%s' cannot be a choice attribute"
                        % inner.key))
                elif inner.key in KEY_TO_FIELD:
                    _parameter(inner, parameters, file, fault_list,
                               position_db)
                else:
                    fault_list.append(Fault(
                        E_FaultKind.VOCABULARY, file, inner.key_position,
                        "unknown key '%s' in choice '%s'"
                        % (inner.key, choice.key)))
            result[choice.key] = TestParameters(**parameters)
        return result

    fault_list.append(Fault(
        E_FaultKind.TYPE, file, entry.key_position,
        "'choices' is a map of choices or a list of names"))
    return {}


def _parameter(entry, parameter_db, file, fault_list, position_db=None):
    """RETURN: None. Converts one test parameter entry into
    'parameter_db', or records a fault. Where 'position_db' is given, the
    key's place is recorded in it -- a value's provenance names a line."""
    key = entry.key
    if position_db is not None:
        position_db[key] = entry.key_position
        if isinstance(entry.node, ObjectNode) and key in ("caps", "build"):
            for inner in entry.node.entry_list:
                position_db["%s.%s" % (key, inner.key)] = \
                                                    inner.key_position
    if key == "pype":
        value = _string(entry, file, fault_list)
        if value is not None: parameter_db["pype"] = value
    elif key == "numeric":
        value = _number(entry, file, fault_list)
        if value is not None:
            if not 0.0 <= value <= 1.0:
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, entry.node.position,
                    "'numeric' is a relative ratio in [0..1]"))
            else:
                parameter_db["numeric"] = float(value)
    elif key in ("eq-pattern", "nothing"):
        value = _string_list(entry, file, fault_list)
        if value is not None: parameter_db[KEY_TO_FIELD[key]] = value
    elif key == "constraints":
        if _off_f(entry.node):
            parameter_db["constraints"] = ()
        else:
            value = _string_list(entry, file, fault_list)
            if value is not None: parameter_db["constraints"] = value
    elif key in ("slash_eqv", "whitespace_eqv", "same",
                 "interactive"):
        value = _bool(entry, file, fault_list)
        if value is not None: parameter_db[KEY_TO_FIELD[key]] = value
    elif key == "build":
        value = _build(entry, file, fault_list)
        if value is not None: parameter_db["build"] = value
    elif key == "caps":
        value = _caps(entry, file, fault_list)
        if value is not None: parameter_db["caps"] = value
    elif key in ("analogy", "comment"):
        _marker_pair(entry, parameter_db, file, fault_list)


def _build(entry, file, fault_list):
    """
    RETURN: Build, from the framework named alone or from the scope.
            None, the value is neither (fault recorded).
    """
    node = entry.node
    if isinstance(node, ScalarNode) and isinstance(node.value, str):
        return Build(framework=node.value)
    if not isinstance(node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, _position_of(node, entry),
            "'build' is a framework name or a scope of 'framework', "
            "'executable' and 'caps'"))
        return None

    field_db = {}
    for inner in node.entry_list:
        if inner.key in ("framework", "executable"):
            value = _string(inner, file, fault_list)
            if value is not None: field_db[inner.key] = value
        elif inner.key == "caps":
            value = _caps(inner, file, fault_list)
            if value is not None: field_db["caps"] = value
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, inner.key_position,
                "unknown key '%s' in 'build'" % inner.key))
    return Build(**field_db)


def _caps(entry, file, fault_list):
    """
    RETURN: Caps, what the author permits the process to spend and reach.
            None, the value is no scope (fault recorded).

    Every field procsitter caps stands here; procsitter owns the defaults,
    and this record holds only what was stated.
    """
    node = entry.node
    if not isinstance(node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, _position_of(node, entry),
            "'caps' is a scope of process caps"))
        return None

    field_db = {}
    for inner in node.entry_list:
        if inner.key in _CAP_POSITIVE_SET:
            value = _number(inner, file, fault_list)
            if value is None: continue
            if value <= 0:
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, inner.node.position,
                    "'%s' must be greater than zero" % inner.key))
                continue
            field_db[inner.key] = _CAP_POSITIVE_SET[inner.key](value)
        elif inner.key == "network":
            value = _bool(inner, file, fault_list)
            if value is not None: field_db["network"] = value
        elif inner.key == "write_directory_list":
            value = _string_list(inner, file, fault_list)
            if value is not None:
                field_db["write_directory_list"] = value
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, inner.key_position,
                "unknown cap '%s'" % inner.key))
    return Caps(**field_db)


#  What each marker pair encloses, for the message that refuses a bad one.
_MARKER_PAIR_DB = {"analogy": "the analogy markers",
                   "comment": "the markers of an ignored line"}


def _marker_pair(entry, parameter_db, file, fault_list):
    """RETURN: None. A marker pair -- 'analogy' and 'comment' alike: two
    elements, the opening and the closing. Absence takes the owner's own
    pair; the empty tuple is OFF, stated.

    Off may be written '[]', 'false', 'no', or an empty value. Absence is
    never off.
    """
    key   = entry.key
    node  = entry.node
    what  = _MARKER_PAIR_DB[key]
    field = KEY_TO_FIELD[key]

    if isinstance(node, ScalarNode) and node.value is True:
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, node.position,
            "'%s = true' says nothing: leave '%s' unstated for %s, or "
            "name the pair" % (key, key, what)))
        return

    if _off_f(node):
        parameter_db[field] = ()
        return

    if isinstance(node, ListNode):
        value = _string_list(entry, file, fault_list)
        if value is None: return
        if len(value) != 2:
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, node.position,
                "'%s' names two markers, the opening and the closing; "
                "%d given" % (key, len(value))))
            return
        parameter_db[field] = value
        return

    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(node, entry),
        "'%s' is a pair of markers, or '[]' for off" % key))


def _target(text, position, file, fault_list, what):
    """
    RETURN: Target, from 'file' or 'file choice' -- the call itself.
            None, the text names no target (fault recorded).
    """
    word_list = text.split()
    if len(word_list) == 1:  return Target(word_list[0])
    if len(word_list) == 2:  return Target(word_list[0], word_list[1])
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, position,
        "'%s' takes a target: a file name, or a file name and a choice "
        "name; '%s' names %d words" % (what, text, len(word_list))))
    return None


def _target_list(entry, file, fault_list):
    """
    RETURN: tuple[Target] | None, the targets of a list-valued key.

    The empty list is a statement: nothing collides.
    """
    text_list = _string_list(entry, file, fault_list)
    if text_list is None: return None
    result = []
    for text in text_list:
        target = _target(text, _position_of(entry.node, entry), file,
                         fault_list, entry.key)
        if target is not None: result.append(target)
    return tuple(result)


def _dependency(entry, file, fault_list):
    """
    RETURN: dict, Target -> tuple[Target] -- what must have RUN before
            each target; 'None' where the value is no object.

    The relation is an ordering and not a success relation; a verdict
    never enters it.
    """
    if not isinstance(entry.node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'dependency' is an object of target -> list of targets"))
        return None

    result = {}
    for inner in entry.node.entry_list:
        target = _target(inner.key, inner.key_position, file, fault_list,
                         "dependency")
        if target is None: continue
        needed = _target_list(inner, file, fault_list)
        if needed is None: continue
        result[target] = needed
    return result


def _default_app(entry, file, fault_list):
    """
    RETURN: [0] TestParameters, what every application of the directory
                receives. It does not overwrite: what an application
                states itself stands.
            [1] dict, key -> Position -- so a value taken from here can
                name the line it stands on.
    """
    if not isinstance(entry.node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'default_app' is a scope of test parameters"))
        return None, {}

    parameters  = {}
    position_db = {}
    for inner in entry.node.entry_list:
        if inner.key in KEY_TO_FIELD:
            _parameter(inner, parameters, file, fault_list, position_db)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, inner.key_position,
                "unknown key '%s' in 'default_app'" % inner.key))
    return TestParameters(**parameters), position_db


def _language_setup(entry, file, fault_list):
    """RETURN: dict, language name -> LanguageSetup."""
    if not isinstance(entry.node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'language-setup' is an object of language names"))
        return {}
    result = {}
    for language in entry.node.entry_list:
        if not isinstance(language.node, ObjectNode):
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, language.key_position,
                "language '%s' must carry an object" % language.key))
            continue
        field_db = {}
        for inner in language.node.entry_list:
            if inner.key in ("interpreter", "coverage", "profiler"):
                value = _string(inner, file, fault_list)
                if value is not None: field_db[inner.key] = value
            else:
                fault_list.append(Fault(
                    E_FaultKind.VOCABULARY, file, inner.key_position,
                    "unknown key '%s' in language '%s'"
                    % (inner.key, language.key)))
        result[language.key] = LanguageSetup(**field_db)
    return result


def _apps(entry, file, fault_list):
    """RETURN: dict, source file name -> TestAppSpec (origin CONF)."""
    if not isinstance(entry.node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'apps' is an object of source file names"))
        return {}
    result = {}
    for app in entry.node.entry_list:
        if not isinstance(app.node, ObjectNode):
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, app.key_position,
                "'apps' entry '%s' must carry an object" % app.key))
            continue
        spec, app_fault_list = validate_header(app.node, file,
                                               origin=E_Origin.CONF,
                                               source_file=app.key)
        fault_list.extend(app_fault_list)
        if spec is not None:
            result[app.key] = spec
    return result


def _off_f(node):
    """
    RETURN: bool, the node says OFF -- '[]', 'false', 'no', 'null',
            'nil', 'none', 'nihil', or a value left empty.

    Absence is NOT off: a key that is not written at all never reaches
    here, and takes its owner's default.
    """
    if isinstance(node, ListNode):   return not node.item_list
    if isinstance(node, ScalarNode): return node.value is False \
                                         or node.value is None
    return False


def _null_f(node):
    """RETURN: bool, the node is bound to nothing."""
    return isinstance(node, ScalarNode) and node.value is None


def _nothing_stated(entry, file, fault_list):
    """RETURN: None. Records the fault of a key bound to nothing where
    something is required."""
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(entry.node, entry),
        "'%s' is bound to nothing; leave it unstated for the default, or "
        "name a value" % entry.key))


def _string(entry, file, fault_list):
    """RETURN: str | None; a fault when the value is not a string."""
    node = entry.node
    if _null_f(node):
        _nothing_stated(entry, file, fault_list)
        return None
    if isinstance(node, ScalarNode) and isinstance(node.value, str):
        return node.value
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(node, entry),
        "'%s' must be a string" % entry.key))
    return None


def _number(entry, file, fault_list):
    """RETURN: int | float | None; a fault when not a number."""
    node = entry.node
    if _null_f(node):
        _nothing_stated(entry, file, fault_list)
        return None
    if isinstance(node, ScalarNode) \
       and isinstance(node.value, (int, float)) \
       and not isinstance(node.value, bool):
        return node.value
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(node, entry),
        "'%s' must be a number" % entry.key))
    return None


def _bool(entry, file, fault_list):
    """RETURN: bool | None; a fault when not a boolean."""
    node = entry.node
    if _null_f(node):
        _nothing_stated(entry, file, fault_list)
        return None
    if isinstance(node, ScalarNode) and isinstance(node.value, bool):
        return node.value
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(node, entry),
        "'%s' must be a boolean" % entry.key))
    return None


def _string_list(entry, file, fault_list):
    """
    RETURN: tuple[str] | None -- from a list of strings, or from a single
            string (normalised); a fault otherwise.
    """
    node = entry.node
    if _null_f(node):
        _nothing_stated(entry, file, fault_list)
        return None
    if isinstance(node, ScalarNode) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ListNode):
        result = []
        for item in node.item_list:
            if isinstance(item, ScalarNode) \
               and isinstance(item.value, str):
                result.append(item.value)
            else:
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, item.position,
                    "'%s' carries strings only" % entry.key))
        return tuple(result)
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, _position_of(node, entry),
        "'%s' must be a string or a list of strings" % entry.key))
    return None


def _position_of(node, entry):
    """RETURN: Position, the node's own if it has one, the key's else."""
    return getattr(node, "position", None) or entry.key_position
