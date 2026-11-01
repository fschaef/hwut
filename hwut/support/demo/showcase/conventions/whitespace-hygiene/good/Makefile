all: build/fw.elf

build/fw.elf: src/filter.c src/units.c
	mkdir -p build
	$(CC) -o $@ $^
