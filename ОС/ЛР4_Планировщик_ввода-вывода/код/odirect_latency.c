/*
 * odirect_latency.c — задержка одиночного прямого чтения 4 КБ (разделы 1.5,
 * 1.6 и 2.3 отчёта). Один поток, O_DIRECT, сначала WARMUP прогревочных
 * чтений, затем SAMPLES измерений. Смещения генерируются детерминированно
 * (фиксированное зерно), поэтому для всех планировщиков набор одинаковый.
 *
 * Сборка: make            Запуск: sudo ./odirect_latency /dev/sdd [samples] [warmup]
 * Вывод:  p50 и p99 в микросекундах; с -v ещё и все отсчёты (CSV).
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifdef __linux__
#include <linux/fs.h>
#endif

#define BLOCK 4096
#define SEED  0x5eed2026u

static uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

/* xorshift32: воспроизводимый набор смещений без зависимости от libc rand() */
static uint32_t rng_state = SEED;
static uint32_t xorshift32(void)
{
    uint32_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return rng_state = x;
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static double percentile(const uint64_t *sorted, size_t n, double p)
{
    /* линейная интерполяция между соседними порядковыми статистиками */
    double pos = p * (double)(n - 1);
    size_t lo = (size_t)pos;
    size_t hi = lo + 1 < n ? lo + 1 : lo;
    double frac = pos - (double)lo;
    return (double)sorted[lo] * (1.0 - frac) + (double)sorted[hi] * frac;
}

static uint64_t device_size(int fd)
{
    struct stat st;
    if (fstat(fd, &st) != 0)
        return 0;
    if (S_ISREG(st.st_mode))
        return (uint64_t)st.st_size;
#ifdef BLKGETSIZE64
    uint64_t sz = 0;
    if (ioctl(fd, BLKGETSIZE64, &sz) == 0)
        return sz;
#endif
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <device|file> [samples=300] [warmup=30] [-v]\n", argv[0]);
        return 2;
    }
    const char *path = argv[1];
    size_t samples = argc > 2 ? strtoul(argv[2], NULL, 10) : 300;
    size_t warmup = argc > 3 ? strtoul(argv[3], NULL, 10) : 30;
    int verbose = argc > 4 && strcmp(argv[4], "-v") == 0;
    if (samples == 0) {
        fprintf(stderr, "samples must be > 0\n");
        return 2;
    }

    int fd = open(path, O_RDONLY | O_DIRECT);
    if (fd < 0) {
        fprintf(stderr, "open(%s, O_DIRECT): %s\n", path, strerror(errno));
        return 1;
    }
    uint64_t size = device_size(fd);
    uint64_t nblocks = size / BLOCK;
    if (nblocks < 2) {
        fprintf(stderr, "%s: слишком мал или размер неизвестен\n", path);
        return 1;
    }

    void *buf = NULL;
    if (posix_memalign(&buf, BLOCK, BLOCK) != 0) {
        fprintf(stderr, "posix_memalign failed\n");
        return 1;
    }
    uint64_t *lat = calloc(samples, sizeof(*lat));
    if (!lat) {
        perror("calloc");
        return 1;
    }

    for (size_t i = 0; i < warmup + samples; ++i) {
        off_t off = (off_t)(xorshift32() % nblocks) * BLOCK;
        uint64_t t0 = now_ns();
        ssize_t r = pread(fd, buf, BLOCK, off);
        uint64_t t1 = now_ns();
        if (r != BLOCK) {
            fprintf(stderr, "pread at %lld: %s\n", (long long)off,
                    r < 0 ? strerror(errno) : "short read");
            return 1;
        }
        if (i >= warmup)
            lat[i - warmup] = t1 - t0;
    }

    if (verbose) {
        puts("sample,latency_ns");
        for (size_t i = 0; i < samples; ++i)
            printf("%zu,%llu\n", i, (unsigned long long)lat[i]);
    }
    qsort(lat, samples, sizeof(*lat), cmp_u64);
    printf("samples=%zu warmup=%zu p50_us=%.1f p99_us=%.1f\n", samples, warmup,
           percentile(lat, samples, 0.50) / 1000.0,
           percentile(lat, samples, 0.99) / 1000.0);

    free(lat);
    free(buf);
    close(fd);
    return 0;
}
