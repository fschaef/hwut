/* lru.h -- a fixed-size LRU cache of small values under one-letter keys,
 * static memory only (for a sensor gateway's last-reading cache).        */
#ifndef LRU_H
#define LRU_H
#define LRU_SIZE 4

int  lru_get(char key, int* value);          /* 1 hit, 0 miss            */
char lru_put(char key, int value);           /* the key evicted, or 0    */
int  lru_dump(char* keys);                   /* most recent first; count */
#endif
