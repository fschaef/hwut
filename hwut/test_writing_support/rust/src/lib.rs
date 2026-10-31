// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: THE PYTHON TEST SUPPORT, IN RUST -- one library crate, 'hwut',
//          one module per Python module ('../README.txt'):
//
//     hwut_runner             hwut_runner.py             the front end of a test
//     deterministic_random    deterministic_random.py    a stream the same everywhere
//     deterministic_timeline  deterministic_timeline.py  races drawn as strings
//     space_iterator          space_iterator.py          every combination of a basis
//     hwut_fsm                hwut_fsm.py                a state machine as the model
//     hwut_hocon              hwut_hocon.py              the HOCON subset, annotated
//     hwut_vterm              hwut_vterm.py              a terminal's screen (libvterm)
//     hwut_pytext             --                         text as Python prints it
//
// The standard library only; the few C functions it needs are declared in
// 'posix' by hand.
//______________________________________________________________________________
pub mod hwut_pytext;
pub mod hwut_runner;
pub mod deterministic_random;
pub mod deterministic_timeline;
pub mod space_iterator;
pub mod hwut_fsm;
pub mod hwut_hocon;
pub mod hwut_vterm;
mod posix;
