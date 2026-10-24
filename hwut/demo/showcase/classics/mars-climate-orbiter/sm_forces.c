/* sm_forces.c -- MODEL of the ground program 'SM_FORCES' ("small forces")
 * of the Mars Climate Orbiter mission (NASA MCO Mishap Investigation Board,
 * Phase I report, 10 Nov 1999). It turns the thruster firings of each
 * angular momentum desaturation (AMD) into the impulse that the navigation
 * software reads from the AMD file. The Software Interface Specification
 * asked for newton-seconds.
 *
 * The model's thrusters are rated 0.2 lbf each (a model value), as a vendor
 * sheet would give it -- in pound-force. UNITS selects (-DUNITS=...):
 *   UNITS_SI          impulse converted to N*s (1 lbf = 4.4482216152605 N),
 *                     tagged 'N*s': what the interface asked for
 *   UNITS_TAGGED      impulse left in lbf*s, and TAGGED 'lbf*s': honest,
 *                     a reader that knows units converts it
 *   UNITS_MCO_1999    impulse left in lbf*s, tagged 'N*s' as the interface
 *                     demands: the number of one unit under the name of
 *                     another -- what flew, by the factor 4.45
 *
 * stdin: the thruster log ('<day> <on-time s>', '#' notes).
 * stdout: the AMD file, one line per event:
 *         'AMD <day> <on-time> s <impulse> <unit>'                         */
#include <stdio.h>

#define UNITS_SI       1
#define UNITS_TAGGED   2
#define UNITS_MCO_1999 3

#define THRUST_LBF   0.2               /* rated thrust, vendor sheet: lbf   */
#define N_PER_LBF    4.4482216152605   /* exact by definition of the lbf    */

int main(void)
{
    char   line[256];
    int    day;
    double on;
    while (fgets(line, sizeof line, stdin)) {
        if (line[0] == '#' || sscanf(line, "%d %lf", &day, &on) != 2) continue;
        double impulse_lbfs = on * THRUST_LBF;
#if   UNITS == UNITS_SI
        printf("AMD %3d %4.1f s %8.4f N*s\n", day, on, impulse_lbfs * N_PER_LBF);
#elif UNITS == UNITS_TAGGED
        printf("AMD %3d %4.1f s %8.4f lbf*s\n", day, on, impulse_lbfs);
#elif UNITS == UNITS_MCO_1999
        printf("AMD %3d %4.1f s %8.4f N*s\n", day, on, impulse_lbfs);
#endif
    }
    return 0;
}
