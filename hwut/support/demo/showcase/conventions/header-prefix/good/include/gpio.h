/* gpio.h -- GPIO pins, module prefix GPIO_ */
#ifndef GPIO_H
#define GPIO_H

#define GPIO_PIN(port, n)   (((port) << 4) | (n))
#define GPIO_LED_RED        GPIO_PIN(1, 5)

void gpio_set(unsigned pin, int level);

#endif /* GPIO_H */
