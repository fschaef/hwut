/* lights.h -- controller of a crossing: main road NS, side road EW with a
 * car sensor. One call per second of the controller's clock.            */
#ifndef LIGHTS_H
#define LIGHTS_H
enum { RED = 0, YELLOW = 1, GREEN = 2 };
typedef void (*show_t)(int t, const char* road, int colour);

void lights_init(show_t show);
void lights_tick(int t, int car_on_ew);   /* car_on_ew: sensor, this second */
#endif
