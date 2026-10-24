/* gpio.h -- GPIO pins, module prefix GPIO_ */
#ifndef __GPIO_H__
#define __GPIO_H__

#define GPIO_PIN(port, n)   (((port) << 4) | (n))
#define GPIO_LED_RED        GPIO_PIN(1, 5)
#define BIT(n)              (1u << (n))

void gpio_set(unsigned pin, int level);

#endif /* GPIO_H */
