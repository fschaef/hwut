/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * THE PRODUCER OF 'protocol.sh clean' -- no test, the service it watches:
 * five clients, each a thread, send a request and get its response, at
 * moments of their own; then the service shuts down. Every line is printed
 * and flushed as it happens: 'protocol.pype' is fed LIVE.
 *
 *     producer.exe          (built by 'on_entry', or 'make producer.exe')
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t        random_state;

static double
uniform(double low, double high)
/* RETURN: double, drawn evenly from [low, high) (splitmix64, under 'lock'). */
{
    uint64_t z;
    pthread_mutex_lock(&lock);
    z = (random_state += 0x9E3779B97F4A7C15ULL);
    pthread_mutex_unlock(&lock);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return low + (high - low) * (double)((z ^ (z >> 31)) >> 11) / 9007199254740992.0;
}

static void
nap(double seconds)
/* RETURN: nothing; the thread slept 'seconds' (below one). */
{
    struct timespec t = { 0, (long)(seconds * 1e9) };
    nanosleep(&t, NULL);
}

static void
say(const char* what, int n)
/* RETURN: nothing; '<what> <n>' printed and flushed, alone on its line. */
{
    pthread_mutex_lock(&lock);
    if( n ) printf("%s %d\n", what, n);
    else    printf("%s\n", what);
    fflush(stdout);
    pthread_mutex_unlock(&lock);
}

static void*
client(void* argument)
/* RETURN: NULL; the client sent its request and got its response. */
{
    int n = (int)(intptr_t)argument;
    nap(uniform(0.0, 0.02));
    say("request", n);
    nap(uniform(0.0, 0.02));
    say("response", n);
    return NULL;
}

int
main(void)
/* RETURN: int, 0 -- five exchanges and 'shutdown' printed. */
{
    struct timespec now;
    pthread_t       pool[5];
    int             n;
    clock_gettime(CLOCK_REALTIME, &now);
    random_state = (uint64_t)now.tv_sec * 1000000000ULL + (uint64_t)now.tv_nsec;
    for(n = 1; n <= 5; ++n) pthread_create(&pool[n - 1], NULL, client, (void*)(intptr_t)n);
    for(n = 1; n <= 5; ++n) pthread_join(pool[n - 1], NULL);
    say("shutdown", 0);
    return 0;
}
