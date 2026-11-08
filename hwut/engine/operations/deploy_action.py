"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE DEPLOY -- what puts the built image where the test reaches it:
       a flash onto a board, a copy onto a target (intend/26 o-40, o-41,
       o-47).

DESCRIPTION
       ONE SUPERVISED CALL of the command the header states,

           deploy = "<command>"   =   deploy { flash = "<command>" }

       run DIRECTLY -- never through make, which turns 77 into 2 -- in the
       directory where the build ran (its image stands there), in the test
       directory where nothing is built.

       IT JUDGES NOTHING. Exit 0 is OK; exit 77 is DEVICE_UNREACHABLE, the
       device the image goes to is absent (the last stderr line is the
       detail); a command not found is DEPLOY_TOOL_NOT_FOUND; a cap
       contains it as DEPLOY_CONTAINED; any other exit is DEPLOY_FAILED.
       That each of these FAILS the application's tests is the plan's
       word: the deploy is a node supporting them (o-47).
______________________________________________________________________________
"""
from dataclasses import dataclass
from pathlib     import Path
from typing      import Optional

from .result          import E_TestRunResult, DEVICE_EXIT_CODE, last_line_of
from ..procsitter.api import Procsitter, E_Containment


@dataclass(frozen=True, slots=True)
class DeployOutcome:
    """What the deploy step produced."""
    report: E_TestRunResult
    record: object                     # the attribution record
    detail: Optional[str] = None       # the last line of stderr, where
                                       # the command said something

    @property
    def succeeded(self):
        """
        RETURN: True,  the command ran to its own good end (exit 0).
                False, otherwise.
        """
        return self.report is E_TestRunResult.OK


def deploy_directory_of(configuration):
    """
    RETURN: Path, where the deploy command runs: the build's own
            directory where the application is built -- the image stands
            there -- the test directory else.
    """
    if configuration.build is not None:
        return Path(configuration.build_directory)
    return Path(configuration.test_directory)


def classify(record):
    """
    RETURN: E_TestRunResult, the brief report of one supervised deploy.
    """
    match record.containment:
        case E_Containment.OK_COMPLETED:
            return E_TestRunResult.OK
        case E_Containment.FAIL_LAUNCH:
            return E_TestRunResult.DEPLOY_TOOL_NOT_FOUND
        case E_Containment.FAIL_COMPLETED:
            if record.exit_code == DEVICE_EXIT_CODE:
                return E_TestRunResult.DEVICE_UNREACHABLE
            return E_TestRunResult.DEPLOY_FAILED
        case _:
            return E_TestRunResult.DEPLOY_CONTAINED   # a resource cap


async def deploy(configuration, stop_event=None):
    """
    RETURN: DeployOutcome, the report of running the application's
            deploy command, its attribution record, and the last line of
            its stderr as the detail (None where it wrote none).

    'configuration' is the TestConfiguration; its '.deploy' is the argv,
    its '.deploy_caps' the caps the deploy runs under (the application's
    where the header states none).
    """
    argv = configuration.deploy
    assert argv, "deploy() called for a test that carries no deploy"

    directory = deploy_directory_of(configuration)
    directory.mkdir(parents=True, exist_ok=True)
    caps = getattr(configuration, "deploy_caps", None) or configuration.caps

    chunk_list = []
    async def on_stderr(chunk):
        """RETURN: None. The chunk kept for the detail."""
        chunk_list.append(chunk)

    record = await Procsitter(caps, work_dir=str(directory)).run(
                 list(argv), stderr_handler=on_stderr,
                 stop_event=stop_event)
    text = b"".join(chunk_list).decode("utf-8", errors="replace")
    return DeployOutcome(report = classify(record),
                         record = record,
                         detail = last_line_of(text))
