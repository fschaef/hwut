/* lights.c -- NS is green by default. A car on EW requests a phase: NS keeps
 * green for at least 10 s, shows yellow 3 s, then both roads stay red 2 s
 * (the all-red clearance), EW gets 8 s green, 3 s yellow, all-red 2 s, and
 * NS is green again. Outputs change through 'show' (lamp drivers).      */
#include "lights.h"

#define MIN_GREEN_NS 10
#define YELLOW_S      3
#define ALL_RED_S     2
#define GREEN_EW      8

enum { NS_G, NS_Y, ALL_R1, EW_G, EW_Y, ALL_R2 };
static int    state, since, waiting;
static show_t show;

static void enter(int t, int s)
{
    state = s; since = 0;
    switch( s ) {
    case NS_G:   show(t, "NS", GREEN);  break;
    case NS_Y:   show(t, "NS", YELLOW); break;
    case ALL_R1: show(t, "NS", RED);    break;
    case EW_G:   show(t, "EW", GREEN);  waiting = 0; break;
    case EW_Y:   show(t, "EW", YELLOW); break;
    case ALL_R2: show(t, "EW", RED);    break;
    }
}

void lights_init(show_t s)
{ show = s; waiting = 0; show(0, "EW", RED); enter(0, NS_G); }

void lights_tick(int t, int car)
{
    waiting |= car;
    ++since;
    switch( state ) {
    case NS_G:   if( waiting && since >= MIN_GREEN_NS ) enter(t, NS_Y); break;
    case NS_Y:   if( since >= YELLOW_S )  enter(t, ALL_R1); break;
    case ALL_R1: if( since >= ALL_RED_S ) enter(t, EW_G);   break;
    case EW_G:   if( since >= GREEN_EW )  enter(t, EW_Y);   break;
    case EW_Y:   if( since >= YELLOW_S )  enter(t, ALL_R2); break;
    case ALL_R2: if( since >= ALL_RED_S ) enter(t, NS_G);   break;
    }
}
