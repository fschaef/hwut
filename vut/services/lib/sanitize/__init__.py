# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
'hwut.sanitize's two further faces, and the commands all three share
(services E-125).

    command.py   the commands -- remove, forget, book, remark, run --
                 each JUDGING AGAIN before it acts; the reader of one
                 line; the re-run trigger. 'hwut.sanitize <command>
                 <entity>' does one, 'hwut.sanitize.apply' a file.
    propose.py   'hwut.sanitize.propose [-o <file>]': ACTS ON NOTHING.
                 Walks the tree and writes what it finds as commands,
                 kind by kind, each block headed by the problem and
                 what its command heals.
    apply.py     'hwut.sanitize.apply <file>': does every command the
                 file still holds -- the reading was the consent.

The judgement of what is insane is 'services/sanitize.py's, one
function per aspect; propose writes what it finds and every command
asks the same function again. One law, one place.
"""
