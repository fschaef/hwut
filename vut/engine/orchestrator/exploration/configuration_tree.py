"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The PLAIN TREE -- typed, slotted, frozen records. The vocabulary is
         stated here, once; the validator checks against it and everything
         downstream reads fields, never string keys.

A field the author did not state is 'None'. Absence is data: the record says
what was CHOSEN; the default table (relation.py) says what happens when
nothing was.

'KEY_TO_FIELD' ties each HOCON key to its record field; keys carry hyphens
where fields carry underscores.
______________________________________________________________________________
"""
from dataclasses import dataclass, replace
from enum        import Enum, auto

from .fault      import Position


class E_Origin(Enum):
    HEADER    = auto()   # the specification stands in the file's header
    CONF      = auto()   # the specification stands under 'apps'
    INTERVIEW = auto()   # the application answered '--hwut-info' (R-44)


#  HOCON key -> TestParameters field.
KEY_TO_FIELD = {
    "build":       "build",
    "caps":        "caps",
    "pype":        "pype",
    "tolerance":   "tolerance",
    "eq-pattern":  "eq_pattern",
    "nothing":     "nothing",
    "analogy":     "analogy",
    "constraints": "constraints",
    "comment":     "comment",
    "same":        "same",
    "interactive": "interactive",
    "execute":     "execute",
    "output":      "output",
}

#  Stated at the ROOT only. Neither is a statement a single choice can
#  make: 'same' is about the SET of choices, 'interactive' about the
#  file's front end.
ROOT_ONLY_KEY_SET = ("same", "interactive")


def _merged(mine, theirs):
    """
    RETURN: the value that stands after 'theirs' overwrites 'mine':
            'mine' where 'theirs' states nothing, 'theirs' where it does,
            and -- for a SCOPE -- the two merged field by field.

    A scope is transparent to the root default at every level: stating one
    field of a scope in a choice leaves its siblings at the root's value.
    """
    if theirs is None:                       return mine
    if mine is None:                         return theirs
    if type(mine) is not type(theirs):       return theirs
    if not hasattr(mine, "merged_with"):     return theirs
    return mine.merged_with(theirs)


class _Scope:
    """Mixin: per-field merging for the frozen scope records."""

    def merged_with(self, other):
        """
        RETURN: a record of this type, every field 'other' states taking
                other's value, scopes merged one level further down.
        """
        return replace(self, **{
            name: _merged(getattr(self, name), getattr(other, name))
            for name in self.__dataclass_fields__
        })


@dataclass(frozen=True, slots=True)
class Caps(_Scope):
    """What a process may spend and may reach: procsitter's parameters.
    Procsitter owns every default here; this record holds only what the
    author stated.

    A cap procsitter cannot enforce refuses the test (R-48)."""
    timeout_sec:          float | None = None
    cpu_sec:              float | None = None
    memory_mb:            int   | None = None
    file_size_mb:         int   | None = None
    child_process_max_n:  int   | None = None
    file_handle_max_n:    int   | None = None
    network:              bool  | None = None
    write_directory_list: tuple | None = None


@dataclass(frozen=True, slots=True)
class Build(_Scope):
    """How the test application comes into being. 'build = "make"' is this
    record with 'framework' alone; the scope form states the rest.

    'caps' here caps the BUILD process; the caps at choice level cap the
    RUN. One noun, one meaning, two places.

    '%' in 'framework' and 'executable' is the SOURCE FILE'S STEM (R-74).
    The coverage target is NOT here: it is the language's word,
    'language-setup.<lang>.coverage_target' (R-73)."""
    framework:  str  | None = None
    executable: str  | None = None
    caps:       Caps | None = None


@dataclass(frozen=True, slots=True)
class Tolerance(_Scope):
    """HOW FAR THE SUBJECT MAY DIFFER AND STILL PASS, per lexical kind
    (R-77). Compare owns every default; this record holds only what the
    author stated.

    'numeric_ratio' the relative ratio two numbers may differ by, in
                    [0..1]; 0 is exact
    'whitespace'    runs of blanks are one blank
    'slash'         a backslash and a slash are the same separator
    """
    numeric_ratio: float | None = None
    whitespace:    bool  | None = None
    slash:         bool  | None = None


@dataclass(frozen=True, slots=True)
class TestParameters(_Scope):
    """One choice's test parameters, as stated. 'None' throughout means:
    nothing stated -- the default table answers at the point of use.

    'analogy' and 'constraints' distinguish absence from OFF: 'None' is
    absence and takes the owner's default; the empty tuple is off, stated.

    'same' and 'interactive' stand at the root only and reach every choice
    through the resolution; a choice never states them itself.
    """
    build:       Build | None = None
    caps:        Caps  | None = None
    pype:        str   | None = None
    tolerance:   Tolerance | None = None
    eq_pattern:  tuple | None = None
    nothing:     tuple | None = None
    analogy:     tuple | None = None
    constraints: tuple | None = None
    comment:     tuple | None = None
    same:        bool  | None = None
    interactive: bool  | None = None
    execute:     str   | None = None
    #  WHAT THE TEST PRODUCES (todo-1). None: '<stdout>' alone.
    #  A stated tuple names the subjects in order; '<stdout>' is the
    #  ONE special name marking the channel, every other entry a FILE
    #  read AFTER the run has ended. '<stderr>' is refused at
    #  validation: STDERR IS NEVER SUBJECT TO TESTING (E-5).
    output:      tuple | None = None

    def overwritten_by(self, other):
        """
        RETURN: TestParameters, self with every field 'other' states
                taking other's value -- the root-default resolution.
                Scopes merge field by field, at every depth (R-26).
        """
        return self.merged_with(other)


@dataclass(frozen=True, slots=True)
class TestAppSpec:
    """One test application as ONE CARRIER states it: unresolved -- the
    root parameters stand beside the per-choice ones.

    'position_db' and 'choice_position_db' hold the place of every key
    the author wrote, so a value's PROVENANCE can name a line."""
    source_file:        str
    title:              str | None
    language:           str | None
    root_parameters:    TestParameters
    choice_db:          dict              # name | None -> TestParameters
    origin:             E_Origin
    position:           Position
    position_db:        dict = None       # key -> Position (root)
    choice_position_db: dict = None       # choice -> {key: Position}


@dataclass(frozen=True, slots=True)
class LanguageSetup:
    """EVERYTHING HWUT DOES WITH ONE LANGUAGE, as 'hwut-root.conf' states
    it (R-73). The entry's NAME is the language, and a file's 'language'
    word selects it by that name.

    'extensions'       the file extensions that select this entry where
                       a header states no 'language'; each with its dot
    'interpreter'      the call for an INTERPRETED test, argv prefix;
                       the language's own name where unstated (R-10)
    'coverage'         the candidate coverage tools, PREFERENCE ORDER;
                       the empty tuple is an answer (coverage D-2)
    'coverage_target'  the COVERAGE-CAPABLE build target, '%' the source
                       file's stem (R-74); under 'hwut.cov' it is built
                       and run in place of 'build.executable'. Unstated
                       for a COMPILED test: noted 'NO_COVERAGE_TARGET'
                       on the book entry, the run continues with the
                       executable (coverage D-19)
    'profiler'         declared, not yet consumed"""
    extensions:      tuple      = ()
    interpreter:     str | None = None
    coverage:        tuple      = ()
    coverage_target: str | None = None
    profiler:        str | None = None


@dataclass(frozen=True, slots=True)
class Target:
    """One test application, or one of its choices: the CALL itself.
    'choice' is 'None' where the target names the file alone, and then
    the target means EVERY choice of that file."""
    file:   str
    choice: str | None = None

    def __str__(self):
        """RETURN: str, the target as an author writes it."""
        if self.choice is None: return self.file
        return "%s %s" % (self.file, self.choice)


@dataclass(frozen=True, slots=True)
class Variant:
    """ONE ALTERNATIVE of a variant group: a scope of test parameters
    stated ASIDE, merged over the base when the alternative is named.

    'group' is the dimension it belongs to. The alternatives of one
    group configure THE SAME parameters -- that is what makes them
    alternatives -- and stating the same fields inside one group is
    required, not a conflict (RATIONALE E-9).
    """
    name:       str
    group:      str
    parameters: object                   # TestParameters
    position:   object     = None


@dataclass(frozen=True, slots=True)
class DirectorySpec:
    """The directory's own keys of 'hwut.conf'.

    'collision' names the applications that cannot run AT THE SAME TIME;
    'dependency' names, per target, what must have RUN FIRST -- an
    ordering relation, and no verdict enters it.

    'default_app' carries test parameters every application of the
    directory receives. It does not overwrite: what an application states
    itself stands.

    'target_db' binds the USER-DEFINED TARGETS of 'hwut.target' (E-7):
    an open-ended namespace of the directory's own, local, never
    inherited. 'on_entry'/'on_exit' are standard targets with their own
    keys and are refused inside it by name.

    'variant_db' holds the VARIANT GROUPS of 'variant_group { }': the
    alternative's name -> Variant. ONE NAMESPACE for every alternative
    of every group, so '--variant=gcov' needs no qualification and two
    groups may not share an alternative name. Two alternatives of ONE
    group named together are refused: they configure one subspace."""
    on_entry:        str | None = None
    on_exit:         str | None = None
    test_directory:  str | None = None
    ignore:          tuple      = ()
    collision:       tuple      = ()     # of Target
    dependency:      dict       = None   # Target -> tuple of Target
    target_db:       dict       = None   # target name -> script (E-7)
    default_app:     object     = None   # TestParameters, or None
    default_app_position_db: dict = None # key -> Position
    variant_db:      dict       = None   # alternative name -> Variant
    language_setup:  dict       = None
    position:        Position   = None


@dataclass(frozen=True, slots=True)
class CTestApp:
    """One test application, RESOLVED: every choice's parameters carry the
    application's own defaults and the directory's folded in. What exists,
    per file.

    'origin_db' maps choice -> {parameter name -> provenance}: where each
    value came from, where that is not the choice's own word. The names
    are the relation table's, so a scope leaf reads 'caps.timeout_sec'."""
    source_file: str
    title:       str | None
    language:    str | None
    choice_db:   dict                     # name | None -> TestParameters
    origin:      E_Origin
    position:    Position
    origin_db:   dict = None              # choice -> {name: str}
    #  R-73: True where 'language' was DERIVED from the file's extension
    #  through 'language-setup', not stated by the header. Never silent.
    language_derived_f: bool = False


@dataclass(frozen=True, slots=True)
class CTestAppSet:
    """What EXISTS in one TEST directory. No selection, no order.

    'misdep_set' holds the cases whose dependencies CANNOT BE MET: those
    in a dependency cycle, those depending on such a case, and those
    naming a target the directory does not offer. Satisfiability is a
    property of the graph alone and is settled here, before anything
    runs."""
    directory:      str
    app_db:         dict                  # source_file -> CTestApp
    directory_spec: DirectorySpec
    misdep_set:     frozenset = frozenset()   # of (source_file, choice)

    def __iter__(self):
        """YIELD: [0] CTestApp  one application, files in sorted order."""
        for name in sorted(self.app_db):
            yield self.app_db[name]


@dataclass(frozen=True, slots=True)
class CTestCase:
    """One (file, choice) pair -- what RUNS. 'choice' is 'None' for the
    choice-less test application; absence is data.

    'misdep_f' says the dependencies cannot be met: the case is selected,
    is reported, and does not run."""
    source_file: str
    choice:      str | None
    parameters:  TestParameters
    origin:      E_Origin
    position:    Position
    misdep_f:    bool = False

    def target(self):
        """RETURN: Target, this case named as an author writes it."""
        return Target(self.source_file, self.choice)

    def token(self):
        """RETURN: str, '[MISDEP]' where the dependencies cannot be met,
        '' else."""
        return "[MISDEP]" if self.misdep_f else ""


@dataclass(frozen=True, slots=True)
class CTestCaseSequence:
    """A flat, ordered sequence of test cases. Run, diff, merge and accept
    each act on one element and read nothing else."""
    case_list: tuple

    def __iter__(self):
        """YIELD: [0] CTestCase  one case, in sequence order."""
        yield from self.case_list

    def __len__(self):
        """RETURN: int, the number of cases."""
        return len(self.case_list)
