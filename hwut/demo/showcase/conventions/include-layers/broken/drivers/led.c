#include "led.h"
#include "gpio.h"
void led_set(int on) { gpio_write(5, on); }
