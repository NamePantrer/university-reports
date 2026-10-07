CC     ?= gcc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra

malloc_bench: malloc_bench.c
	$(CC) $(CFLAGS) -o $@ $<

# полный прогон: 4 аллокатора -> 4 CSV -> 2 графика
run: malloc_bench
	./run_allocators.sh

table:
	python3 summary_table.py

clean:
	rm -f malloc_bench *.csv compare_*.png

.PHONY: run table clean
