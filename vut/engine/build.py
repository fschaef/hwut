"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE:
"""

class Basic:
    """
    Basic Build procedure for an application which does not require a build to
    exist. This holds for test applications written in interpreted languages,
    for example.
    """

    def __init__(self, file_name_list):
        pass

    def initiate(self, log):
        pass

    async def wait_result(self, file_name):
        assert file_name in self.file_name_list

        if self.access(file_name): verdict = E_Verdict.BUILD_SUCCESS
        else:                      verdict = E_Verdict.BUILD_APP_NOT_EXIST
        return verdict, 0 # 0sec build time


class Null(Basic):
    """
    Not-A-Build Procedure. If assigned, it signifies that no build procedure
    has been specified.
    """

    def initiate(self, log):
        assert False

    async def wait_result(self):
        assert False


class ToolBasic(Basic):
    """
    Build procedure that uses a system tool, such as 'make'.
    """

    def __init__(self, file_name_list, command_line):
        self.start_time_sec = 0
        self.max_time_sec   = hwut_system.BUILD_MAX_TIME_SEC
        self.command_line   = command_line
        BuildBasic.__init__(self, file_name_list)

    def initiate(self, log):
        self.process        = popen(command_line)
        self.start_time_sec = time.time()

    async def wait_result(self, file_name):
        assert file_name in self.file_name_list

        while 1 + 1 == 2:
            if   self.__access(file_name):  verdict = E_Verdict.BUILD_SUCCESS; break
            elif self.__terminated():       verdict = E_Verdict.BUILD_FAILURE; break
            elif self.__timeout():          verdict = E_Verdict.BUILD_TIMEOUT; break
            elif self.__storage_at_limit(): verdict = E_Verdict.BUILD_STORAGE_LIMIT; break

#wait asyncio.sleep(self.__next_time_delta_sec())

        return verdict, self.build_process.time_elapsed()

    def time_elapsed(self):
        return time.time() - self.start_time_sec

    def __timeout(self):
        return self.time_elapsed() > self.max_time_sec

    def __terminated(self):
        return self.process.done()

    def __storage_at_limit(self):
        return file_system.storage_at_limit()

    def __next_time_delta_sec(self):
        # Increase waiting interval, but remain in 0.01ms to 1sec.
        return max(min(0.01, self.time_elapsed() * 1.5), 1.0)


class Tool_Make(ToolBasic):
    """
    Build procedure to build applications using 'Make' build system tool.
    """
    def __init__(self, file_name_list):
        # Apply the system's 'make' application with as many jobs as file names (-jN).
        command_line = [ hwut_system.BUILD_APP_MAKE, "-j%i"  % len(file_name_list) ]
        command_line += file_name_list
        ToolBasic.__init__(file_name_list, command_line)


def get_instructions(app_list):
    """Receives a list of App-s. Each app tells about the '.build_type' which it requires
    in order to be built. This function determines a 'build.Basic' procedure that can
    produce the given applications. Possibly, a procedure can produces multiple apps at
    once.
    """

    def _get(build_type, app_list):
        file_name_list = [ app.file_name for app in app_list ]

        if   build_type == E_BuildType.SCRIPT: build = Basic(file_name_list)
        elif build_type == E_BuildType.MAKE:   build = Tool_Make(make + file_name_list)
        else:                                  assert False

        for app in app_list:
            app.relate_to_build_process(build)

        return build

    # Categorize build that can be accomplished within one single call.
    db = defaultdict(list)
    for app in app_list:
        db[app.build_type].append(app)

    return [ _get(build_type, app_list) for build_type, app_list in db.items() ]



