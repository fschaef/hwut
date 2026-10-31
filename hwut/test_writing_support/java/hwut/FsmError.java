/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A MODEL THAT CANNOT BE MEANT -- 'FsmError' of 'python/hwut_fsm.py';
 *          its message is Python's text, named with its line where read from
 *          text. Thrown where the model is read or a word it never names is
 *          asked for, never while events are fired. Python derives it from
 *          ValueError; here from IllegalArgumentException.
 * _____________________________________________________________________________
 */
package hwut;

public class FsmError extends IllegalArgumentException {
    /** RETURN: FsmError carrying 'message', Python's text. */
    public FsmError(String message) { super(message); }
}
