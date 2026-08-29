"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE BUILD -- a step inside provision, for a COMPILED test.

DESCRIPTION
       A build is ONE supervised call plus two things supervision knows
       nothing about: an argv built from the enumerated build vocabulary,
       and POST-EXIT ACCOUNTING of the targets against a declared
       contract. It is an ARRANGEMENT of procsitter, never a kind of it.

       IT RUNS IN ITS OWN DIRECTORY, 'BUILD/<source-file-stem>' (README
       3). So a build writes no object file where the application writes
       its output, and two tests of one source tree never share a build
       directory -- which is what lets them run concurrently without a
       lock.

       IT JUDGES NOTHING. It reports what happened -- the tool was not
       found, the tool failed, a cap contained it, a declared target is
       absent -- as one token of the brief vocabulary. Whether that makes
       the TEST fail is decided above, and it does: a failed build is a
       failed test (README 8).
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   enum        import Enum
from   pathlib     import Path
from   typing      import Optional, Sequence

from   .result                  import E_TestRunResult
from   ..procsitter.procsitter  import (Procsitter,
                                        E_Containment)


class E_BuildSystem(Enum):
    """The ENUMERATED build vocabulary -- small, meant to GROW. The value
    is the default tool command; 'BuildConfig.tool' overrides it (a path,
    'gmake', 'mingw32-make', ...).

    GENERATOR is the GENERAL member: any program called to produce the
    targets -- a code generator, 'protoc', a script. It has NO default
    command, so 'tool' is mandatory, and its targets are NOT passed on
    the command line: for it 'target_list' is purely the ACCOUNTING
    CONTRACT of what must exist afterwards.
    """
    MAKE      = "make"
    NINJA     = "ninja"
    CMAKE     = "cmake"
    MESON     = "meson"
    BAZEL     = "bazel"
    SCONS     = "scons"
    MSBUILD   = "msbuild"
    GENERATOR = "<generator>"

    def __str__(self):
        """RETURN: str, the build system's token."""
        return self.value


@dataclass(frozen=True)
class BuildConfig:
    """The build's OWN struct, held verbatim by the test's configuration
    (README 2.7). None there means: this test is not COMPILED."""
    build_system:  E_BuildSystem
    target_list:   Sequence[str]        = field(default_factory=tuple)
    argument_list: Sequence[str]        = field(default_factory=tuple)
    tool:          Optional[str]        = None   # mandatory for GENERATOR


@dataclass(frozen=True)
class BuildOutcome:
    """What the build step produced. Folded into 'Provision' above."""
    report:               E_TestRunResult
    record:               object                # the attribution record
    built_target_list:    Sequence[str] = field(default_factory=tuple)
    missing_target_list:  Sequence[str] = field(default_factory=tuple)

    @property
    def succeeded(self):
        """
        RETURN: True,  the tool ran to its own good end AND every declared
                       target is present.
                False, otherwise.
        """
        return self.report is E_TestRunResult.OK


def make_argv(config):
    """
    RETURN: list[str], the build system's argv for the requested targets,
            CONSTRUCTED from the enumerated vocabulary.

    Raises AssertionError if GENERATOR is used without a tool: it has no
    default command, and guessing one would launch something nobody
    named. No quoting is applied -- this is the argv, executed directly.
    """
    if config.build_system is E_BuildSystem.GENERATOR:
        assert config.tool is not None, \
               "GENERATOR has no default command; 'tool' is mandatory"
        tool = config.tool
    else:
        tool = config.tool if config.tool is not None \
                           else config.build_system.value

    #  THREE SHAPES, one vocabulary. A build system differs in WHERE the
    #  subcommand sits and HOW targets are spelled -- never in escaping,
    #  because there is none: this is the argv, executed directly.
    #      plain      make | ninja | scons        tool [args] [targets]
    #      subcommand cmake | meson | bazel       tool SUB [args] [targets]
    #      folded     msbuild                     tool [args] -t:a;b
    argv = [tool]
    if   config.build_system is E_BuildSystem.CMAKE:
        argv += ["--build", "."]
    elif config.build_system is E_BuildSystem.MESON:
        argv += ["compile"]
    elif config.build_system is E_BuildSystem.BAZEL:
        argv += ["build"]
    argv += [str(a) for a in config.argument_list]

    if config.build_system is E_BuildSystem.GENERATOR:
        return argv                       # targets are accounting only
    target_list = [str(t) for t in config.target_list]
    if target_list:
        if   config.build_system is E_BuildSystem.CMAKE:
            argv.append("--target")
            argv += target_list
        elif config.build_system is E_BuildSystem.MSBUILD:
            argv.append("-t:" + ";".join(target_list))
        else:
            argv += target_list
    return argv


def classify(record, missing_target_list):
    """
    RETURN: E_TestRunResult, the brief report of one supervised build.

    Tool reasons outrank target reasons: a tool that never ran cannot be
    blamed for a target it never reached.
    """
    match record.containment:
        case E_Containment.FAIL_LAUNCH:
            return E_TestRunResult.BUILD_TOOL_NOT_FOUND
        case E_Containment.FAIL_COMPLETED:
            return E_TestRunResult.BUILD_FAILED        # nonzero exit
        case E_Containment.OK_COMPLETED:
            pass                                       # on to the targets
        case _:
            return E_TestRunResult.BUILD_CONTAINED     # a resource cap

    if missing_target_list:
        return E_TestRunResult.TARGET_NOT_BUILT
    return E_TestRunResult.OK


def account_targets(build_directory, target_list):
    """
    RETURN: (built, missing), two lists of target names, split by whether
            the target EXISTS under 'build_directory' after the tool
            finished.

    POST-EXIT: the filesystem is asked once, when the tool is gone. A
    tool that reports success and produced nothing is caught here, and
    only here.
    """
    built, missing = [], []
    for target in target_list:
        path = Path(build_directory) / str(target)
        (built if path.exists() else missing).append(str(target))
    return built, missing


async def build(configuration, caps=None, stop_event=None, observer=None):
    """
    RETURN: BuildOutcome, what the build step produced -- its report, its
            attribution record, and the target accounting.

    'configuration' is the TestConfiguration; its '.build' carries the
    build's own struct and its '.build_directory' is where the tool runs.
    'caps' overrides the test's own caps for the build alone.

    The build directory is CREATED if absent: a first build of a test has
    nowhere to run yet.
    """
    from .observer import notify

    build_configuration = configuration.build
    assert build_configuration is not None, \
           "build() called for a test that carries no build configuration"

    directory = configuration.build_directory
    directory.mkdir(parents=True, exist_ok=True)

    procsitter = Procsitter(caps if caps is not None else configuration.caps,
                            work_dir=str(directory))
    record     = await procsitter.run(make_argv(build_configuration),
                                      stop_event=stop_event)

    built, missing = account_targets(directory,
                                     build_configuration.target_list)
    report  = classify(record, missing)
    outcome = BuildOutcome(report              = report,
                           record              = record,
                           built_target_list   = tuple(built),
                           missing_target_list = tuple(missing))
    notify(observer, "built", report)
    return outcome
