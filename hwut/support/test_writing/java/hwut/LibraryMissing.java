/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: 'libvterm' WAS NOT FOUND -- neither by the system's search nor
 *          under the name HWUT_LIBVTERM gives: 'LibraryMissing' of
 *          'python/hwut_vterm.py'. Its message is Python's text: what is
 *          wrong, then how to install the library ('Vterm.INSTALL_HINT').
 * _____________________________________________________________________________
 */
package hwut;

public class LibraryMissing extends RuntimeException {
    /** RETURN: LibraryMissing carrying 'message', Python's text. */
    public LibraryMissing(String message) { super(message); }
}
