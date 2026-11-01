#include "hal/gpio.h"
#include "../services/telemetry.h"
void gpio_write(int pin, int level) { (void)pin; telemetry_push(level); }
