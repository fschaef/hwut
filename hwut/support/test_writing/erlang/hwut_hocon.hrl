%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% THE ANNOTATED TREE of 'hwut_hocon' -- Python's dataclasses as records.
%% A position is {Line, Column}, 1-based, as an editor counts (columns in
%% characters). A scalar's value: a binary (str), an integer, a float,
%% true/false, none (nothing), or inf/'-inf' where a decimal exceeds the
%% double (Python's float('inf'); Erlang holds no infinity).
%%_____________________________________________________________________________
-record(source_line,  {text          :: binary(),        %% one line as read
                       line          :: pos_integer(),   %% its number in the file
                       column_offset :: non_neg_integer()}). %% removed before 'text'
-record(hocon_object, {position, entry_list = [] :: list()}).
-record(hocon_list,   {position, item_list  = [] :: list()}).
-record(hocon_scalar, {position, value}).
-record(hocon_entry,  {key :: binary(), key_position, node}).
-record(hocon_fault,  {kind :: syntax | refused, file :: binary(), position,
                       message :: binary()}).
