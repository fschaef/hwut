"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WALLFLOWER LIST (X-SILENT) -- the files no carrier speaks for,
         one path per line relative to the call directory, in
         'hwut-wallflowers.txt' there, so that

             hwut.config.ignore $(cat hwut-wallflowers.txt)

         settles them. Written by every face that finds them ('hwut.run',
         'hwut.report'); the note that names the file is display's
         ('engine/display/plain.py', 'wallflower_note_list').

A LIST STANDS ONLY FOR THE LAST FACE THAT LOOKED: the writer removes an
earlier one before that face can speak. A '.txt' is never a candidate
(finder), so the list never lists itself.
______________________________________________________________________________
"""
import os

WALLFLOWERS_NAME = "hwut-wallflowers.txt"


def wallflowers_writer(write_error):
    """
    RETURN: callable, taking the sorted path list, writing it to
            WALLFLOWERS_NAME in the call directory, and returning that
            name -- or None where the file cannot be written, which is
            said through 'write_error'.

    The stale list of an earlier face is removed HERE, on creation.
    """
    try:
        os.remove(WALLFLOWERS_NAME)
    except FileNotFoundError:
        pass
    except OSError as error:
        write_error("FAULT: the stale '%s' cannot be removed (%s)"
                    % (WALLFLOWERS_NAME, error))

    def write_wallflowers(path_list):
        """RETURN: str,  WALLFLOWERS_NAME, the list written.
                  None, the file could not be written."""
        try:
            with open(WALLFLOWERS_NAME, "w", encoding="utf-8") as fh:
                fh.write("".join("%s\n" % path for path in path_list))
        except OSError as error:
            write_error("FAULT: '%s' cannot be written (%s); the paths "
                        "follow in the note" % (WALLFLOWERS_NAME, error))
            return None
        return WALLFLOWERS_NAME

    return write_wallflowers
