"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE CONFIGURATION OF ONE TEST APPLICATION -- what the test IS.

DESCRIPTION
       Three worlds are kept apart (README 2.7): this CONFIGURATION is
       the test's design; the STORE holds the artifacts; products travel
       step to step and are never persisted. The configuration is written
       once and only read thereafter.

       AGGREGATION, NOT RESTATEMENT. Every sub-component's own struct is
       held VERBATIM -- procsitter's caps are a 'ProcsitterConfig', not
       ten numbers copied out and translated back. A field is declared by
       the component that ENFORCES it, once.

       HANDED IN COMPLETE. Nothing here reads a configuration file or
       resolves shorthand. What builds a 'TestConfiguration' is OUTSIDE;
       this module states the shape it must produce, and checks it.

       THE UNIT IS THE TEST APPLICATION, identified by its source file.
       There is no configuration per run and none per choice: one serves
       every run of that application, and the choice database lives
       inside it.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   enum        import Enum
from   pathlib     import Path
from   typing      import Mapping, Optional, Sequence

from   ..procsitter.procsitter import ProcsitterConfig


class E_SourceKind(Enum):
    """How the test application becomes a command line."""
    EXECUTABLE  = "executable"    # run directly
    INTERPRETED = "interpreted"   # an interpreter argv prefix runs it
    COMPILED    = "compiled"      # built first, then the artifact runs

    def __str__(self):
        """
        RETURN: str, the lowercase source-kind token ('executable',
                     'interpreted', 'compiled').
        """
        return self.value


@dataclass(frozen=True)
class TestChoiceConfiguration:
    """ONE SCENARIO of the application: how its output is FREED of
    channel distortion, in the two ways there are.

    'canonicalisers' carry UNDERSTANDING -- a pype argv per subject that
    rewrites a stream into its canonical form, after which comparison is
    byte-exact. A subject absent from the map is compared RAW, raw being
    canonical for it.

    'compare' carries TOLERANCE -- compare's own Configuration, held
    verbatim, ONE per choice: the compare setup of this scenario.

    COMPLETE AS HANDED IN. An author who states one canonicaliser for the
    whole test states it once; whatever builds the configuration puts it
    into every entry. Nothing here resolves a default.
    """
    canonicalisers: Mapping[str, Sequence[str]] = field(default_factory=dict)
    compare:        object                      = None


@dataclass(frozen=True)
class TestConfiguration:
    """THE TEST APPLICATION, and every run of it."""
    source_file:    str
    source_kind:    E_SourceKind
    test_directory: str
    caps:           ProcsitterConfig
    choice_db:      Mapping[Optional[str], TestChoiceConfiguration]
    interpreter:    Optional[Sequence[str]] = None   # INTERPRETED only
    build:          object                  = None   # COMPILED only
    store:          object                  = None   # None: do not record

    @property
    def stem(self):
        """
        RETURN: str, the source file's stem -- 'parse' for 'parse.c'.

        It KEYS THE BUILD DIRECTORY, so stems must be unique across the
        tests that share a directory. This object sees one test and
        cannot check that; the check belongs where configurations are
        made.
        """
        return Path(self.source_file).stem

    @property
    def build_directory(self):
        """
        RETURN: Path, where THIS test's build runs: 'BUILD/<stem>' under
                the test directory.

        One build directory per test is what lets different tests run
        concurrently without a lock.
        """
        return Path(self.test_directory) / "BUILD" / self.stem

    @property
    def output_directory(self):
        """
        RETURN: Path, 'OUT/' under the test directory -- where the
                application's output files land.
        """
        return Path(self.test_directory) / "OUT"

    @property
    def has_choices(self):
        """
        RETURN: True,  the application is called once per named choice.
                False, it is called ONCE with no choice argument.

        Answered by the single 'None' key: a test that mentions no
        choices has '{None: ...}' and nothing else.
        """
        return None not in self.choice_db

    def choice_configuration(self, choice_name):
        """
        RETURN: TestChoiceConfiguration, the entry of 'choice_name'.

        Raises KeyError if the choice is not in the database. 'None' is
        the key of a test without choices.
        """
        return self.choice_db[choice_name]


class ConfigurationError(ValueError):
    """A configuration that cannot serve any goal -- raised where it is
    HANDED IN, before a single step runs, never at step seven."""
    pass


def verify(configuration):
    """
    RETURN: None, the configuration is servable.

    Raises ConfigurationError naming the ONE first fault. Checks only
    what this object can see -- one test application. Whether two tests
    collide in 'BUILD/<stem>' is invisible here and belongs above.
    """
    c = configuration

    if not c.choice_db:
        raise ConfigurationError("choice_db is empty: no call is described. "
                                 "A test without choices has the single key "
                                 "'None'.")
    if None in c.choice_db and len(c.choice_db) != 1:
        named = sorted(str(x) for x in c.choice_db if x is not None)
        raise ConfigurationError(
            "choice_db mixes the 'None' choice with named choices %s. "
            "'None' means NO choice argument is passed, so it cannot "
            "stand beside choices that are." % (named,))

    if c.source_kind is E_SourceKind.INTERPRETED and not c.interpreter:
        raise ConfigurationError("source_kind is INTERPRETED but no "
                                 "interpreter argv prefix is given.")
    if c.source_kind is not E_SourceKind.INTERPRETED and c.interpreter:
        raise ConfigurationError("an interpreter argv prefix is given, but "
                                 "source_kind is %s -- it is read only for "
                                 "INTERPRETED." % c.source_kind)
    if c.source_kind is E_SourceKind.COMPILED and c.build is None:
        raise ConfigurationError("source_kind is COMPILED but no build "
                                 "configuration is given.")
    if c.source_kind is not E_SourceKind.COMPILED and c.build is not None:
        raise ConfigurationError("a build configuration is given, but "
                                 "source_kind is %s -- a build happens only "
                                 "for COMPILED." % c.source_kind)

    for name, entry in c.choice_db.items():
        if isinstance(entry, TestChoiceConfiguration): continue
        raise ConfigurationError("choice %r maps to %s, not a "
                                 "TestChoiceConfiguration."
                                 % (name, type(entry).__name__))
