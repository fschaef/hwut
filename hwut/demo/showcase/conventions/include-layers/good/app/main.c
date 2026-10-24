#include "app/app_config.h"
#include "drivers/led.h"
#include "services/telemetry.h"
#include "services/logger.h"
int main(void) { led_set(1); log_line("up"); for (int i = 0; i < 3; i++) telemetry_push(i); return 0; }
