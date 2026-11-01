/* lru.c -- slots in a doubly linked list, most recently used at the head.
 * get: a hit moves the slot to the head. put: an existing key is updated
 * and moved to the head; a new key takes a free slot, or the tail's.     */
#include "lru.h"

typedef struct { char key; int value; int prev, next; } slot_t;
static slot_t slot[LRU_SIZE];
static int    head = -1, tail = -1, used = 0;

static void unlink_slot(int i)
{
    if( slot[i].prev >= 0 ) slot[slot[i].prev].next = slot[i].next; else head = slot[i].next;
    if( slot[i].next >= 0 ) slot[slot[i].next].prev = slot[i].prev; else tail = slot[i].prev;
}
static void push_head(int i)
{
    slot[i].prev = -1; slot[i].next = head;
    if( head >= 0 ) slot[head].prev = i;
    head = i;
    if( tail < 0 ) tail = i;
}
static int find(char key)
{ int i; for( i = head; i >= 0; i = slot[i].next ) if( slot[i].key == key ) return i; return -1; }

int lru_get(char key, int* value)
{
    int i = find(key);
    if( i < 0 ) return 0;
    unlink_slot(i); push_head(i);
    *value = slot[i].value;
    return 1;
}

char lru_put(char key, int value)
{
    char evicted = 0;
    int  i = find(key);
    if( i >= 0 )                  { unlink_slot(i); }
    else if( used < LRU_SIZE )    { i = used++; }
    else                          { i = tail; evicted = slot[i].key; unlink_slot(i); }
    slot[i].key = key; slot[i].value = value;
    push_head(i);
    return evicted;
}

int lru_dump(char* keys)
{ int n = 0, i; for( i = head; i >= 0; i = slot[i].next ) keys[n++] = slot[i].key; keys[n] = 0; return n; }
