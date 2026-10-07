/*
 * malloc_bench.c — бенчмарк из приложения А отчёта ЛР6.
 * Для 503 размеров блока (16 Б .. 4 МБ) измеряет медиану и 95-й процентиль
 * времени malloc, медиану malloc с касанием памяти и медиану free.
 * Каждое измерение — пакет из BATCH выделений, время делится на BATCH.
 * Вывод — CSV в stdout; имя аллокатора берётся из ALLOCATOR_NAME.
 * Альтернативные аллокаторы подключаются через LD_PRELOAD (см. run_allocators.sh).
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define ITERATIONS 300
#define WARMUP 30
#define BATCH 32
#define MAX_SIZES 503

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b) {
    const uint64_t x = *(const uint64_t *)a;
    const uint64_t y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static uint64_t median_u64(uint64_t *v, size_t n) {
    qsort(v, n, sizeof(v[0]), cmp_u64);
    if (n & 1U)
        return v[n / 2];
    return (v[n / 2 - 1] + v[n / 2]) / 2;
}

static uint64_t p95_u64(uint64_t *v, size_t n) {
    qsort(v, n, sizeof(v[0]), cmp_u64);
    size_t i = (95 * n + 99) / 100;
    if (i == 0) i = 1;
    if (i > n) i = n;
    return v[i - 1];
}

/* 256 размеров 16..4096 шаг 16, 120 размеров до 64 КБ шаг 512,
 * 120 размеров до 1 МБ шаг 8192 и 7 крупных до 4 МБ — всего 503 */
static size_t make_sizes(size_t *sizes) {
    size_t n = 0;
    for (size_t s = 16; s <= 4096; s += 16)
        sizes[n++] = s;
    for (size_t s = 4608; s <= 65536; s += 512)
        sizes[n++] = s;
    for (size_t s = 73728; s <= 1048576; s += 8192)
        sizes[n++] = s;

    const size_t tail[] = {
        1310720, 1638400, 2048000, 2560000,
        3200000, 4000000, 4194304
    };
    for (size_t i = 0; i < sizeof(tail) / sizeof(tail[0]); ++i)
        sizes[n++] = tail[i];
    return n;
}

static int alloc_batch(void **p, size_t size) {
    for (int i = 0; i < BATCH; ++i) {
        p[i] = malloc(size);
        if (p[i] == NULL) {
            for (int j = 0; j < i; ++j) free(p[j]);
            return -1;
        }
    }
    return 0;
}

static void free_batch(void **p) {
    for (int i = 0; i < BATCH; ++i)
        free(p[i]);
}

static int measure_size(size_t size,
                        uint64_t *malloc_median,
                        uint64_t *malloc_p95,
                        uint64_t *touch_median,
                        uint64_t *free_median) {
    uint64_t tm[ITERATIONS];
    uint64_t tt[ITERATIONS];
    uint64_t tf[ITERATIONS];
    void *p[BATCH];

    for (int w = 0; w < WARMUP; ++w) {
        if (alloc_batch(p, size) != 0) return -1;
        for (int i = 0; i < BATCH; ++i)
            ((volatile unsigned char *)p[i])[0] = (unsigned char)i;
        free_batch(p);
    }

    for (int r = 0; r < ITERATIONS; ++r) {
        uint64_t t0 = now_ns();
        if (alloc_batch(p, size) != 0) return -1;
        uint64_t t1 = now_ns();
        tm[r] = (t1 - t0) / BATCH;

        t0 = now_ns();
        free_batch(p);
        t1 = now_ns();
        tf[r] = (t1 - t0) / BATCH;

        t0 = now_ns();
        if (alloc_batch(p, size) != 0) return -1;
        for (int i = 0; i < BATCH; ++i)
            ((volatile unsigned char *)p[i])[0] = (unsigned char)(r + i);
        t1 = now_ns();
        tt[r] = (t1 - t0) / BATCH;
        free_batch(p);
    }

    uint64_t tm_copy[ITERATIONS];
    memcpy(tm_copy, tm, sizeof(tm));
    *malloc_median = median_u64(tm, ITERATIONS);
    *malloc_p95 = p95_u64(tm_copy, ITERATIONS);
    *touch_median = median_u64(tt, ITERATIONS);
    *free_median = median_u64(tf, ITERATIONS);
    return 0;
}

int main(void) {
    size_t sizes[MAX_SIZES];
    const size_t n = make_sizes(sizes);
    const char *name = getenv("ALLOCATOR_NAME");
    if (name == NULL || *name == '\0') name = "unknown";

    printf("# allocator=%s iterations=%d warmup=%d max_size=%zu\n",
           name, ITERATIONS, WARMUP, sizes[n - 1]);
    printf("size_bytes,malloc_median_ns,malloc_p95_ns,"
           "touch_median_ns,free_median_ns\n");

    for (size_t i = 0; i < n; ++i) {
        uint64_t mm, p95, touch, fr;
        if (measure_size(sizes[i], &mm, &p95, &touch, &fr) != 0) {
            fprintf(stderr, "allocation failed for %zu bytes\n", sizes[i]);
            return 1;
        }
        printf("%zu,%llu,%llu,%llu,%llu\n",
               sizes[i],
               (unsigned long long)mm,
               (unsigned long long)p95,
               (unsigned long long)touch,
               (unsigned long long)fr);
        fflush(stdout);
    }
    return 0;
}
