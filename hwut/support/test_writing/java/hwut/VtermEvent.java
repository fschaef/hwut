/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: ONE THING THE TERMINAL DID, as libvterm reports it (the RAW layer)
 *          -- 'Event' of 'python/hwut_vterm.py'.
 *
 *     kind  "damage"    rows 'row'..'rowEnd' and columns 'column'..'columnEnd'
 *                       changed, the ends EXCLUDED
 *           "cursor"    the cursor stands at ('row', 'column'); 'value' (a
 *                       Boolean) says whether it is visible
 *           "property"  the property 'name' is now 'value' (an Integer; null
 *                       where the value is a text)
 *           "bell"      the bell rang
 * Fields a kind does not use are null.
 * _____________________________________________________________________________
 */
package hwut;

public record VtermEvent(String kind, Integer row, Integer column, Integer rowEnd, Integer columnEnd,
                         String name, Object value) {

    /** RETURN: String, the event on one line, as Python's test prints it. */
    @Override public String toString() {
        return switch (kind) {
            case "damage"   -> "damage    rows " + row + ".." + rowEnd + "  columns " + column + ".." + columnEnd;
            case "cursor"   -> "cursor    (" + row + ", " + column + ")" + (Boolean.TRUE.equals(value) ? "" : "  hidden");
            case "property" -> "property  " + name + " = " + PyText.str(value);
            default         -> kind;
        };
    }
}
