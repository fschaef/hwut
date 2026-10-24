#include "util.h"
int util_clamp(int value, int low, int high)
{ return value < low ? low : value > high ? high : value; }
