"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE KEYED MERGE SESSION -- a viewer tier where the author
         points, marks and TAKES, rather than answering a prompt.

DESCRIPTION
       The tier splits at one seam. 'act', 'state', 'region', 'reduce'
       and 'project' are PURE: no terminal, no 'prompt_toolkit', no I/O,
       so every ruling they carry is testable as a list of acts in and a
       state out. 'driver' is the glue that lets 'prompt_toolkit' own
       the layout, the scrolling and the search, and pushes the
       projection into its Buffers ONE WAY -- our state never reads its
       viewport offset back.
______________________________________________________________________________
"""
