/* calcd.c -- a small request server on stdin/stdout, as many tools embed
 * one (an LSP server, a build daemon). Each line 'req <id> <op> <arg>' is
 * handed to a pool of 3 worker threads; each worker answers
 * 'res <id> <result>' WHEN IT IS DONE -- answers come in any order.
 * 'quit' waits for the workers and ends with 'bye <answers given>'.
 *     ops:  fib <n>   upper <word>   rev <word>   len <word>             */
#include <ctype.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define QUEUE_MAX 64
typedef struct { int id; char op[16]; char arg[64]; } job_t;

static job_t           queue[QUEUE_MAX];
static int             head = 0, tail = 0, quitting = 0, answered = 0;
static pthread_mutex_t lock    = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  ready   = PTHREAD_COND_INITIALIZER;
static pthread_mutex_t out     = PTHREAD_MUTEX_INITIALIZER;

static long fib(int n) { long a = 0, b = 1; while( n-- > 0 ) { long c = a + b; a = b; b = c; } return a; }

static void* worker(void* seed_p)
{
    unsigned seed = (unsigned)(size_t)seed_p;
    for(;;) {
        job_t job; char result[96]; int i, n;
        pthread_mutex_lock(&lock);
        while( head == tail && !quitting ) pthread_cond_wait(&ready, &lock);
        if( head == tail ) { pthread_mutex_unlock(&lock); return NULL; }
        job = queue[head++ % QUEUE_MAX];
        pthread_mutex_unlock(&lock);

        usleep(1000 + rand_r(&seed) % 15000);                  /* the work */
        n = (int)strlen(job.arg);
        if     ( !strcmp(job.op, "fib") )   snprintf(result, sizeof result, "%ld", fib(atoi(job.arg)));
        else if( !strcmp(job.op, "upper") ) { for( i = 0; i <= n; ++i ) result[i] = (char)toupper((unsigned char)job.arg[i]); }
        else if( !strcmp(job.op, "rev") )   { for( i = 0; i < n; ++i ) result[i] = job.arg[n - 1 - i]; result[n] = 0; }
        else if( !strcmp(job.op, "len") )   snprintf(result, sizeof result, "%d", n);
        else                                snprintf(result, sizeof result, "error:unknown-op");

        pthread_mutex_lock(&out);
        printf("res %d %s\n", job.id, result); fflush(stdout); ++answered;
        pthread_mutex_unlock(&out);
    }
}

int main(void)
{
    pthread_t pool[3]; char line[160]; int i;
    for( i = 0; i < 3; ++i ) pthread_create(&pool[i], NULL, worker, (void*)(size_t)(time(NULL) ^ (i * 7919) ^ getpid()));
    while( fgets(line, sizeof line, stdin) ) {
        job_t job;
        if( !strncmp(line, "quit", 4) ) break;
        if( sscanf(line, "req %d %15s %63s", &job.id, job.op, job.arg) != 3 ) continue;
        pthread_mutex_lock(&lock);
        queue[tail++ % QUEUE_MAX] = job;
        pthread_cond_signal(&ready);
        pthread_mutex_unlock(&lock);
    }
    pthread_mutex_lock(&lock); quitting = 1; pthread_cond_broadcast(&ready); pthread_mutex_unlock(&lock);
    for( i = 0; i < 3; ++i ) pthread_join(pool[i], NULL);
    printf("bye %d\n", answered);
    return 0;
}
