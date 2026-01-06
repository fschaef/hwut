#! /usr/bin/env python3
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

from vut.engine.compare.configuration import Configuration
import vut.engine.compare.main        as     main
import vut.engine.compare.TEST.racing as     racing


if "--hwut-info" in sys.argv:
    print("Async Racing: is_equivalent Early Abort;")
    print("CHOICES: subject-slow, nominal-slow, jittery;")
    sys.exit()

async def run_test(sub_timeline_pattern, nom_timeline_pattern):
    config = Configuration()
    
    # Test Data: 100 lines, with a mismatch at line 5 (Index 4)
    subject_time_list = [f"Line {i}\n" for i in range(100)]
    subject_time_list[4] = "SALTY\n"
    nominal_line_list = [f"Line {i}\n" for i in range(100)]
    nominal_line_list[4] = "SWEET\n"

    subject_timeline = (sub_timeline_pattern * 7)[:500] 
    nominal_timeline = (nom_timeline_pattern * 7)[:500]

    subject,          \
    nominal,          \
    dispatcher_handle = racing.prepare_dispatcher(subject_timeline, subject_time_list, 
                                                  nominal_timeline, nominal_line_list)

    try:
        verdict = await main.is_equivalent(config, subject, nominal)
    finally:
        await racing.cleanup(dispatcher_handle)

    print(f"Verdict: {verdict}")
    
    # VERIFICATION: Did we stop early?
    # We started with 100 lines. 
    # Mismatch is at line 5. 
    # Even with buffering, we shouldn't have read all 100 lines.
    print(f"Lines Consumed - Subject: {subject.lines_consumed}, Nominal: {nominal.lines_consumed}")

if __name__ == "__main__":
    if "subject-slow" in sys.argv:
        # Subject is sparse (Priority 1), Nominal is dense
        asyncio.run(run_test("1    ", "111111"))
        print("NOTE: The of NOMINAL at time 21 is ok, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
    elif "nominal-slow" in sys.argv:
        # Subject is dense, Nominal is sparse
        asyncio.run(run_test("1111111", "1    "))
        print("NOTE: The eat of SUBJECT at time 21 is ok, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
    else: 
        # both-jittery: Irregular staggered patterns
        asyncio.run(run_test("1 1   1 ", "  1 1 1 "))
        print("NOTE: The eat SUBJECT at time 14, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
