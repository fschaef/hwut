/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: ONE CELL OF THE SCREEN, AS PLAIN VALUES -- 'Cell' of
 *          'python/hwut_vterm.py'.
 *
 * 'text' is what stands in it -- "" for a cell nothing was written to, and
 * for the right half of a wide character. 'foreground' and 'background' are
 * an Rgb, or null where the cell wears the terminal's default -- also where
 * a program asked by number for the very colour the default is.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayList;
import java.util.List;

public record VtermCell(String text, int width, boolean boldF, boolean italicF, boolean underlineF,
                        boolean blinkF, boolean reverseF, boolean concealF, boolean strikeF,
                        Rgb foreground, Rgb background) {

    /** A colour as red, green, blue; printed as Python prints the tuple. */
    public record Rgb(int red, int green, int blue) {
        /** RETURN: String, '(red, green, blue)'. */
        @Override public String toString() { return "(" + red + ", " + green + ", " + blue + ")"; }
    }

    /** RETURN: boolean, the flag of the attribute 'name' (a key of
     *          'Vterm.ATTRIBUTE_SGR_DB'); false for any other name. */
    public boolean attribute(String name) {
        return switch (name) {
            case "bold"      -> boldF;
            case "italic"    -> italicF;
            case "underline" -> underlineF;
            case "blink"     -> blinkF;
            case "reverse"   -> reverseF;
            case "conceal"   -> concealF;
            case "strike"    -> strikeF;
            default          -> false;
        };
    }

    /** RETURN: String, the attributes that are set, by name, in the order of
     *          'Vterm.ATTRIBUTE_SGR_DB', separated by blanks -- 'bold
     *          reverse'; "" where none is set. */
    public String attributeText() {
        List<String> set = new ArrayList<>();
        for (String name : Vterm.ATTRIBUTE_SGR_DB.keySet()) if (attribute(name)) set.add(name);
        return String.join(" ", set);
    }
}
