"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
"""

class App:
    def __init__(self, file_name, build_type):
        self.file_name     = Filename
        self.build_type    = build_type
        self.build_process = BuildProcedureNone()

    def relate_to_build_process(self, build):
        self.build_process = build

    async def wait_presence(self):
        pass
## return wait self.build_process.wait_result(self.file_name)

async def do(directory, selector):
    """Performs the task of testing a set of test applications from a given
    'directory'. Related events are logged through the 'CTestChannel'.
    """
    with inform.CTestChannel(directory) as log:
        try:
            os.chdir(directory)
        except:
            log.directory_does_not_exist()
            return

        test_list = selector.do(_get_all_test_list(directory))
        run_test_list(test_list, log)

async def run(log, test_list):
    """Runs a list of given tests. First, build instructions are derived to
    efficiently build the set of required applications (if necessary). Then,
    tests are executed. All testing is reported to the 'CTestChannel' log.
    """

    # Derive a set of build instructions for a given set of executables.
    for instruction in build.get_instructions(j.app for j in test_list):
        instruction.initiate(log)

    # Wait for test's executable to exist and perform test execution
    asyncio.gather(*(execute(test, log) for test in test_list))


async def execute(test, log):
    """Waits for the test application to be made, then executes the test
    application and compares its output with the nominal output.
    """
    verdict, build_time = await test.executable.wait_presence()

    if verdict != E_Verdict.BUILD_SUCCESS:
        assert verdict in (E_Verdict.BUILD_FAILURE, E_Verdict.BUILD_TIMEOUT, E_Verdict.BUILD_APP_NOT_EXIST)
        report = CTestReport(test, verdict, build_time)
    else:
        report = await test.perform_test(build_time)

    log.test_result(report)

