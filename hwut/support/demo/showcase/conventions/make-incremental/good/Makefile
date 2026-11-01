# Hand-written dependencies -- the reviewer's question: are they complete?
CC     ?= gcc
CFLAGS ?= -O2 -Wall
OBJ    := main.o util.o log.o

app: $(OBJ)
	$(CC) -o $@ $(OBJ)

main.o: main.c log.h util.h
	$(CC) $(CFLAGS) -c -o $@ main.c

util.o: util.c util.h
	$(CC) $(CFLAGS) -c -o $@ util.c

log.o: log.c log.h util.h
	$(CC) $(CFLAGS) -c -o $@ log.c

.PHONY: clean
clean:
	rm -f app $(OBJ)
