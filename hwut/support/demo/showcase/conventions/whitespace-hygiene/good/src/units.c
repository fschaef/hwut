#include <stdio.h>

void print_temperature(float celsius)
{
    printf("%.1f °C\n", celsius);     /* non-ASCII inside a string: fine */
}
