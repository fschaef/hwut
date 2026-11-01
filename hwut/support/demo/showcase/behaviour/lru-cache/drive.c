/* drive.c -- stdin: 'get K' / 'put K V' lines. Prints per op:
 *   <op> <key> <hit|miss|-> <value|-> <evicted|-> <keys, most recent first> */
#include <stdio.h>
#include "lru.h"

int main(void)
{
    char op[8], key, keys[LRU_SIZE + 1]; int value;
    while( scanf("%7s %c", op, &key) == 2 ) {
        if( op[0] == 'g' ) {
            int hit = lru_get(key, &value);
            lru_dump(keys);
            if( hit ) printf("get %c hit %d - %s\n", key, value, keys);
            else      printf("get %c miss - - %s\n", key, keys);
        } else {
            char ev;
            scanf("%d", &value);
            ev = lru_put(key, value);
            lru_dump(keys);
            printf("put %c - %d %c %s\n", key, value, ev ? ev : '-', keys);
        }
    }
    return 0;
}
