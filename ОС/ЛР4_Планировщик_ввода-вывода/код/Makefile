CC      ?= gcc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra

all: odirect_latency parallel_direct_read

odirect_latency: odirect_latency.c
	$(CC) $(CFLAGS) -o $@ $<

parallel_direct_read: parallel_direct_read.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f odirect_latency parallel_direct_read

.PHONY: all clean
