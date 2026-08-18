"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       The supervised BUILD: 'make' (and friends) as an application of
       THE SUPERVISED SYSTEM CALL.

THE INTERFACE
       One door; input = configuration, output = result -- the same
       pattern as the judged test application run
       (sandbox_test_app.py):

           config  'SandboxConfigBuild'   -- THE COMPLETE INPUT: the
                                             build system, the targets
                                             to build, the supervised
                                             call.
           result  'SandboxResultBuild'   -- THE COMPLETE OUTPUT: the
                                             targets ACTUALLY BUILT
                                             (present after the task
                                             finished), the missing
                                             ones, the attribution
                                             record, THE BRIEF REPORT.

           result = await run_build(config)

DESCRIPTION
       THE GROUND is the supervised system call, 'Sandbox.run()'
       (sandbox.py) -- a build is an ordinary supervised call: wall
       clock against hangs, caps against runaway recursion, process
       hygiene against leftovers, stderr tail captured as the WHY of
       a failure. This module adds ONLY the build vocabulary:

           the build system   an ENUMERATED tool ('E_BuildSystem'),
                              never a free command string -- the
                              command line is CONSTRUCTED, the caller
                              composes data, not plumbing. The
                              GENERAL member is GENERATOR: any
                              program called in a sandbox to
                              generate the targets;
           the targets        the names handed to the tool (for
                              GENERATOR: the accounting contract
                              only), and -- after the run -- the
                              ACCOUNTING: which of them exist as
                              files in the work directory, which do
                              not.

       Targets are accounted POST-EXIT only, like output files of a
       test run: a target may be incomplete at any moment while the
       build lives. A PHONY target ('clean', 'all') is a request to
       the build system, not a file -- it never appears in
       '.built_target_list'; account phony builds by '.record.ok'.

       Verdicts and reasons follow the house rule -- nothing
       disappears, THE BRIEF REPORT names the failure:

           build-tool-not-found   the tool could not be launched
           build-contained        a resource cap struck (the record
                                  names the resource)
           build-failed           the tool completed with nonzero
                                  exit ('.record.stderr_tail' holds
                                  the WHY)
           target-not-built       tool exit 0, yet a requested target
                                  is not present post-exit
"""
import os
import shlex
from   dataclasses import dataclass, field
from   enum        import Enum
from   typing      import Optional

from   .sandbox import Sandbox, SandboxResult, E_Containment

from   vut.auxiliary.test_run_result import E_TestRunResult


class E_BuildSystem(Enum):
    """The ENUMERATED build vocabulary -- small, meant to GROW.
    The value is the default tool command; 'SandboxConfigBuild.tool'
    overrides it (path, 'gmake', 'mingw32-make', ...).

    GENERATOR is the GENERAL member: any program called in a sandbox
    to generate the targets (a code generator, 'protoc', a script).
    It has NO default command -- 'tool' is MANDATORY; the targets are
    NOT passed on the command line (the generator's arguments are
    'argument_list'); 'target_list' is purely the ACCOUNTING
    CONTRACT: what must exist after the task finished.
    """
    MAKE      = "make"
    NINJA     = "ninja"
    CMAKE     = "cmake"
    GENERATOR = "<generator>"     # no default command; tool mandatory


@dataclass
class SandboxConfigBuild:
    """RETURN: --. THE COMPLETE INPUT of a supervised build -- the
                   interface definition: hand this to 'run_build()',
                   receive a 'SandboxResultBuild'.

    build_system   E_BuildSystem: WHICH tool builds -- enumerated,
                   never a free command string.
    target_list    the targets handed to the tool, in order; empty:
                   the tool's default target. File targets are
                   accounted post-exit; phony targets are not files
                   (module docstring). For GENERATOR: purely the
                   ACCOUNTING CONTRACT -- never passed to the tool.
    sandbox        the supervised call: Sandbox(config, work_dir) --
                   the work_dir is where the build runs and where
                   targets are accounted.
    tool           command override for the build system (a path, or
                   'gmake'); None: the enum's default command.
                   MANDATORY for GENERATOR (one command word; its
                   arguments go into 'argument_list').
    argument_list  extra arguments, quoted and placed BEFORE the
                   targets ('-j4' for make, '--config Release' for
                   cmake --build); for GENERATOR: THE arguments of
                   the generator call.
    """
    build_system:  E_BuildSystem
    target_list:   list
    sandbox:       Sandbox
    tool:          Optional[str] = None
    argument_list: list          = field(default_factory=list)


@dataclass
class SandboxResultBuild:
    """RETURN: --. THE COMPLETE OUTPUT of a supervised build: the
                   accounting of the requested targets AFTER the task
                   finished, the attribution record, THE BRIEF REPORT
                   -- nothing disappears.
    """
    record:              SandboxResult   # THE ATTRIBUTION RECORD of
                                         # the supervised build call
    command_line:        str             # the CONSTRUCTED command
    built_target_list:   tuple = ()      # requested targets that EXIST
                                         # in the work dir post-exit,
                                         # in request order
    missing_target_list: tuple = ()      # requested targets that do
                                         # NOT -- the mismatch, NAMED
    report:              E_TestRunResult = E_TestRunResult.OK
                                         # THE BRIEF REPORT: 'ok' or
                                         # the reason token

    @property
    def verdict(self) -> bool:
        """
        RETURN: True,  the build tool COMPLETED with exit 0 AND every
                       requested target is present post-exit.
                False, else.
        """
        return self.record.ok and not self.missing_target_list


def _make_command_line(config: SandboxConfigBuild) -> str:
    """
    RETURN: str, the build system's command line for the requested
            targets -- CONSTRUCTED from the enumerated vocabulary;
            arguments and targets quoted. For GENERATOR the targets
            are NOT part of the command line (accounting contract
            only).
    """
    if config.build_system is E_BuildSystem.GENERATOR:
        assert config.tool is not None, \
               "GENERATOR has no default command; 'tool' is mandatory"
        tool = config.tool
    else:
        tool = config.tool if config.tool is not None \
               else config.build_system.value

    part_list = [shlex.quote(tool)]
    if config.build_system is E_BuildSystem.CMAKE:
        part_list += ["--build", "."]
    part_list += [shlex.quote(str(a)) for a in config.argument_list]

    if config.build_system is E_BuildSystem.GENERATOR:
        return " ".join(part_list)
    target_list = [shlex.quote(str(t)) for t in config.target_list]
    if target_list:
        if config.build_system is E_BuildSystem.CMAKE:
            part_list.append("--target")
        part_list += target_list
    return " ".join(part_list)


def _classify(record: SandboxResult, missing_target_list) \
        -> E_TestRunResult:
    """
    RETURN: E_TestRunResult, THE BRIEF REPORT of one supervised
            build: 'ok' or the reason of failure -- tool reasons
            outrank target reasons.
    """
    if record.containment is E_Containment.LAUNCH_FAILED:
        return E_TestRunResult.BUILD_TOOL_NOT_FOUND
    if record.containment is not E_Containment.COMPLETED:
        return E_TestRunResult.BUILD_CONTAINED
    if record.exit_code != 0:
        return E_TestRunResult.BUILD_FAILED
    if missing_target_list:
        return E_TestRunResult.TARGET_NOT_BUILT
    return E_TestRunResult.OK


async def run_build(config: SandboxConfigBuild) -> SandboxResultBuild:
    """
    RETURN: SandboxResultBuild, THE COMPLETE OUTPUT: the targets
            actually built (present after the task finished), the
            missing ones NAMED, the attribution record, THE BRIEF
            REPORT.

    THE DOOR of this module: input = configuration, output = result.
    The build runs as ONE supervised call in the sandbox's work
    directory; stdout is drained, stderr's tail is captured into the
    record (the WHY of a failing build). Targets are accounted
    POST-EXIT only.
    """
    command_line = _make_command_line(config)
    record       = await config.sandbox.run(command_line)

    work_dir = config.sandbox.work_dir
    built_target_list   = []
    missing_target_list = []
    for target in config.target_list:
        if os.path.exists(os.path.join(work_dir, str(target))):
            built_target_list.append(str(target))
        else:
            missing_target_list.append(str(target))

    return SandboxResultBuild(
        record              = record,
        command_line        = command_line,
        built_target_list   = tuple(built_target_list),
        missing_target_list = tuple(missing_target_list),
        report              = _classify(record, missing_target_list))
