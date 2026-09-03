"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE
       A KILL NAMES ITS CAP (O-19), ON EVERY ROAD (O-21). The one
       translation of procsitter's containment into the run's report
       token, and the one sentence of numbers that goes with it --
       shared by the plain road ('stage_execute') and the multi road
       ('multi_execute'), so that no road can fall back to "killed by
       the supervisor" while another names the cap.
______________________________________________________________________________
"""
from   ...procsitter.api   import E_Containment
from   ..result            import E_TestRunResult


#  Which cap a containment names (O-19).
CONTAINMENT_TOKEN_DB = {
    E_Containment.FAIL_WALL_CLOCK_EXCEEDED: E_TestRunResult.TEST_APP_WALL_CLOCK_EXCEEDED,
    E_Containment.FAIL_CPU_TIME_EXCEEDED:   E_TestRunResult.TEST_APP_CPU_TIME_EXCEEDED,
    E_Containment.FAIL_MEMORY_EXCEEDED:     E_TestRunResult.TEST_APP_MEMORY_EXCEEDED,
    E_Containment.FAIL_FILE_SIZE_EXCEEDED:  E_TestRunResult.TEST_APP_FILE_SIZE_EXCEEDED,
    E_Containment.FAIL_PIDS_EXCEEDED:       E_TestRunResult.TEST_APP_PIDS_EXCEEDED,
    E_Containment.FAIL_DISK_USAGE_EXCEEDED: E_TestRunResult.TEST_APP_DISK_EXCEEDED,
}


def detail_of(record, caps):
    """
    RETURN: str, the cap that was hit and how far the run went past it,
                 e.g. 'cap 512 MB, peak 1069 MB' -- from the record's
                 peaks and the caps in force
            None, where the containment names no cap this can measure.

    A PEAK IS WHAT THIS MACHINE SAW (E-36): the detail is spoken, in
    HINTS and the log, and never written to the book.
    """
    c = record.containment
    if c is E_Containment.FAIL_MEMORY_EXCEEDED:
        peak = record.peak_memory_mb
        return "cap %s MB, peak %s MB" % (caps.max_memory_mb,
                                          "?" if peak is None else "%.0f" % peak)
    if c is E_Containment.FAIL_WALL_CLOCK_EXCEEDED:
        return "cap %s s, ran %.1f s" % (caps.max_wall_clock_sec,
                                          record.wall_clock_sec)
    if c is E_Containment.FAIL_CPU_TIME_EXCEEDED:
        used = record.cpu_time_sec
        return "cap %s s cpu, used %s s" % (caps.max_cpu_time_sec,
                                            "?" if used is None else "%.1f" % used)
    if c is E_Containment.FAIL_FILE_SIZE_EXCEEDED:
        return "cap %s MB per file" % caps.max_file_size_mb
    if c is E_Containment.FAIL_PIDS_EXCEEDED:
        return "cap %s, peak %s" % (caps.max_pids,
                                   "?" if record.peak_pids is None else record.peak_pids)
    if c is E_Containment.FAIL_DISK_USAGE_EXCEEDED:
        peak = record.peak_disk_mb
        return "cap %s MB, peak %s MB" % (caps.max_disk_mb,
                                          "?" if peak is None else "%.0f" % peak)
    return None




def token_of(containment):
    """
    RETURN: E_TestRunResult, the report token for a containment that
            ended the call: the cap it names where procsitter can name
            one, 'TEST_APP_CONTAINED' for a containment this table does
            not know. The caller decides whether the containment ended
            anything at all (OK_COMPLETED and FAIL_COMPLETED are not
            kills).
    """
    return CONTAINMENT_TOKEN_DB.get(containment, E_TestRunResult.TEST_APP_CONTAINED)
