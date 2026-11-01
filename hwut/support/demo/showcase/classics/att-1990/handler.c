/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * ---------------------------------------------------------------------------
 * handler.c -- the incoming-message step of a 4ESS-like switch, modelled on
 * the published account of the AT&T outage of 15 January 1990.
 *
 *     int handle(int sender, int write_busy, const int *out_of_service,
 *                int *in_service_request)
 *
 * RETURN: 0, the message was processed;
 *         1, the optional-parameter work ran on pointers that were never
 *            set up -- the switch's data is overwritten and it RESETS.
 *
 * 'sender' is the switch the message comes from; 'out_of_service[sender]'
 * is this switch's status map entry for it; 'write_busy' says that the
 * ring write buffer is not yet empty -- the previous message is still
 * being worked on. 'in service' is SENT to the status map through that
 * buffer ('in_service_request[sender] = 1'): the map changes only once
 * the buffer has been written, a few milliseconds later.
 *
 * FIXED=0  the code as shipped: the 'break' inside the 'if' inside the
 *          'case' was meant to leave the 'if'. C's 'break' leaves the
 *          enclosing 'switch': setting up the parameter pointers is
 *          skipped, and the work after the switch uses them.
 * FIXED=1  the 'break' gone: the message is processed in either case; the
 *          status map is updated the next time the buffer is empty.
 * ------------------------------------------------------------------------ */
#ifndef FIXED
#   define FIXED 0
#endif

enum { MSG_INCOMING = 1 };

static const char parameter_buffer[] = "optional parameters";

int handle(int sender, int write_busy, const int *out_of_service,
           int *in_service_request)
{
    const char *parameter = 0;      /* set up by processing the message */
    int         message   = MSG_INCOMING;

    switch (message) {
    case MSG_INCOMING:
        if (out_of_service[sender]) {
            if (!write_busy) {
                in_service_request[sender] = 1;  /* send 'in service' to the map */
            } else {
#if ! FIXED
                break;      /* meant: leave the 'if' -- leaves the 'switch' */
#endif
            }
        }
        parameter = parameter_buffer;         /* process the message, set up
                                               * the optional parameters  */
        break;
    default:
        break;
    }
    /* do the optional parameter work */
    if (parameter == 0) return 1;             /* stale pointer: data overwritten */
    return 0;
}
