"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WALLFLOWER LISTS (X-SILENT) -- per test directory, the files
         no carrier speaks for, in '<directory>/TMP/wallflowers.txt':
         a '#' header saying what they are and how to settle them, then
         one './../<name>' per line. The './' is the list's own ground
         (the wishlist reader's rule), so the list reads right wherever
         it is read from:

             hwut.config.ignore --wishlist TEST/TMP/wallflowers.txt
             hwut.config.ignore --wallflowers         every list below

         Written by every face that explores ('hwut.run', 'hwut.report');
         the NOTE that points here is display's
         ('engine/display/plain.py', 'wallflower_note_list').

A LIST IS DELETABLE: it lives in 'TMP', hwut's transient ground, and
stands only where the last face that looked found wallflowers. An
explored directory with none has its list removed.
______________________________________________________________________________
"""
import os

WALLFLOWERS_PATH = os.path.join("TMP", "wallflowers.txt")
WALLFLOWERS_GLOB = "**/TMP/wallflowers.txt"

HEADER = """\
#  WALLFLOWERS: files in this test directory that are none of
#     - ignored,       named under 'ignore' in its hwut.conf,
#     - a test,        named under 'apps' in its hwut.conf,
#     - self-declared, carrying a '@hwut { }' block.
#  hwut asks nothing of them. This file is deletable; the next run
#  writes it again where wallflowers still stand.
#
#  To ignore passive helper files, from this test directory:
#     > hwut.config.ignore --wishlist TMP/wallflowers.txt
#  or every list in a tree at once, from above it:
#     > hwut.config.ignore --wallflowers
#  To make a file a test application: name it under 'apps' in this
#  directory's hwut.conf.
#
"""


def wallflowers_writer(write_error):
    """
    RETURN: callable, taking {directory: [name, ...]} for EVERY directory
            the face explored -- 'directory' as reachable from the call
            directory, the list possibly empty -- and returning
            WALLFLOWERS_GLOB where every list stands as it should, None
            where one could not be written or removed, which is said
            through 'write_error'.
    """
    def write_wallflowers(directory_db):
        """RETURN: str,  WALLFLOWERS_GLOB, every list as it should stand.
                  None, one could not be written or removed."""
        ok_f = True
        for directory, name_list in directory_db.items():
            path = os.path.join(directory, WALLFLOWERS_PATH)
            try:
                if not name_list:
                    if os.path.exists(path): os.remove(path)
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(HEADER + "".join("./../%s\n" % name
                                              for name in sorted(name_list)))
            except OSError as error:
                write_error("FAULT: '%s' cannot be written (%s)"
                            % (path, error))
                ok_f = False
        return WALLFLOWERS_GLOB if ok_f else None

    return write_wallflowers


def wallflower_list_paths(root):
    """
    YIELD: [0] str   the path of every wallflower list below 'root', walk
                     order sorted -- '<directory>/TMP/wallflowers.txt'.
    """
    for directory, dir_list, file_list in os.walk(root):
        dir_list.sort()
        if os.path.basename(directory) == "TMP" \
           and "wallflowers.txt" in file_list:
            yield os.path.join(directory, "wallflowers.txt")
