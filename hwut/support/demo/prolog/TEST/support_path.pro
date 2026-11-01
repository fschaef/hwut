/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: WHERE THE PROLOG TEST SUPPORT STANDS -- named here, once, for
             every test of this directory that uses it ('garage.pro',
             'screen.pro'):

        :- use_module('support_path.pro').
        :- use_module(hwut('hwut_runner.pro')).

    SWI-Prolog has no environment variable that extends its library path
    (measured: 'boot/init.pl' of 9.0.4 reads none; 'swipl -p alias=dir'
    is a command-line option, and hwut writes the command line). So the
    alias 'hwut' is defined here: HWUT_SUPPORT_PROLOG, where it is set,
    wins; only where it is not is the path below used -- relative to this
    file's directory, or as written where it is absolute.
    ___________________________________________________________________________
*/
:- module(support_path, []).

:- prolog_load_context(directory, Here), ( getenv('HWUT_SUPPORT_PROLOG', At) -> true ; At = '../../../test_writing/prolog' ), absolute_file_name(At, Dir, [relative_to(Here), file_type(directory)]), asserta(user:file_search_path(hwut, Dir)).   % HWUT-SUPPORT-PATH
