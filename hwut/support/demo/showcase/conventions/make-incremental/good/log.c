#include <stdio.h>
#include "log.h"
void log_value(const char* name, int value)
{ printf("%s = %d\n", name, util_clamp(value, -99, 99)); }
