#include <stdio.h>
#include "services/telemetry.h"
#include "services/logger.h"
#include "../drivers/modem.h"
void telemetry_push(int value) { char b[32]; snprintf(b, sizeof b, "AT+SEND=%d", value); modem_send(b); log_line(b); }
