# Makefile of a small firmware project.
# House rule: every target is reachable from 'all', or it is named in
# STANDALONE; every target that does not build a file is .PHONY.

STANDALONE := clean distclean flash help
.PHONY: all firmware docs test $(STANDALONE)

CC  ?= arm-none-eabi-gcc
OBJ := build/main.o build/uart.o build/spi.o

all: firmware docs test

firmware: build/fw.elf

build/fw.elf: $(OBJ)
	$(CC) -o $@ $^

build/%.o: src/%.c src/board.h
	$(CC) -c -o $@ $<

docs: build/manual.html

build/manual.html: doc/manual.md
	pandoc -o $@ $<

test: build/fw.elf
	./run-tests.sh build/fw.elf

clean:
	rm -rf build

distclean: clean
	rm -f config.mk

flash: firmware
	openocd -f board.cfg -c "program build/fw.elf verify reset exit"

help:
	@echo "all firmware docs test clean distclean flash help"
