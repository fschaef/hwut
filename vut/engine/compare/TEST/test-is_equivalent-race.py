#! /usr/bin/env python3
#
# hwut {
#     title      = "Async Racing: is_equivalent Early Abort"
#     choices    = ["jittery", "nominal-slow", "subject-slow"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Testing 'is_equivalent' early abort under race conditions.

DESCRIPTION:
    This test verifies that the equivalence check aborts as soon as a mismatch
    is found, even if one provider is significantly faster than the other.
    
    The TriggerDispatcher ensures that the "Fast" provider pushes many lines
    into the buffer, while the "Slow" provider lags behind. The test succeeds
    only if the engine stops reading before consuming the entire stream.

CHOICES: subject-slow, nominal-slow, both-jittery;
________________________________________________________________________________
"""
import sys
import asyncio

sys.path.insert(0, "../../../../")

from   vut.engine.compare.configuration import Configuration
import vut.engine.compare.main        as     main
import vut.engine.compare.TEST.line_provider as line_provider
from   vut.language_support.python.deterministic_random import DeterministicStream


async def run_test(subject_timeline, nominal_timeline):
    config = Configuration()
    
    # Test Data: 100 lines, with a mismatch at line 5 (Index 4)
    n = 25
    subject_line_list      = [""] * n
    subject_line_list[:4]  = [f"Line {i}\n" for i in range(4)]
    subject_line_list[4]   = "SALTY"
    subject_line_list[5:n] = [f"SALTY {i-4}\n" for i in range(5, n)]
    nominal_line_list      = [""] * n
    nominal_line_list[:4]  = [f"Line {i}\n" for i in range(4)]
    nominal_line_list[4]   = "SWEET"
    nominal_line_list[5:n] = [f"SWEET {i-4}\n" for i in range(5, n)]

    subject,          \
    nominal,          \
    dispatcher_handle = line_provider.prepare_dispatcher(subject_timeline, subject_line_list, 
                                                  nominal_timeline, nominal_line_list)

    try:
        verdict = await main.is_equivalent(config, subject, nominal)
    finally:
        await line_provider.cleanup(dispatcher_handle)

    print(f"Verdict: {verdict}")
    
    # VERIFICATION: Did we stop early?
    # We started with 100 lines. 
    # Mismatch is at line 5. 
    # Even with buffering, we shouldn't have read all 100 lines.
    print(f"Lines Consumed - Subject: {subject.lines_consumed}, Nominal: {nominal.lines_consumed}")

if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("Async Racing: is_equivalent Early Abort;")
        print("CHOICES: subject-slow, nominal-slow, jittery;")
        sys.exit()
    elif "subject-slow" in sys.argv:
        # Subject is sparse (Priority 1), Nominal is dense
        asyncio.run(run_test("1   "*10, "1111"*10))
    elif "nominal-slow" in sys.argv:
        # Subject is dense, Nominal is sparse
        asyncio.run(run_test("11111"*10, "1    "*10))
    elif "jittery" in sys.argv: 
        rg = DeterministicStream(seed=17)
        t_sub = "".join(rg.select("12  ") for _ in range(80))
        t_nom = "".join(rg.select("12  ") for _ in range(80))
        # both-jittery: Irregular staggered patterns
        asyncio.run(run_test(t_sub, t_nom))
    else:
        assert False
