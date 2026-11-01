#include <stdio.h>

void print_temperature(float celsius)
{
    float größe = celsius;
    printf("%.1f °C\n", größe);       /* non-ASCII inside a string: fine */
}
