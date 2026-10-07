/*
 * parallel_direct_read.c — нагрузка из раздела 2.3 отчёта: NPROC процессов
 * одновременно читают устройство прямым доступом (O_DIRECT), каждый по
 * BLOCKS блоков размером 128 КБ из своей непересекающейся области.
 * По умолчанию 8 x 400 x 128 КБ = 400 МиБ. Печатается общее время в мс.
 *
 * Запуск: sudo ./parallel_direct_read /dev/sdd [nproc=8] [blocks=400]
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define BS (128 * 1024)

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static int reader(const char *path, int idx, long blocks)
{
    int fd = open(path, O_RDONLY | O_DIRECT);
    if (fd < 0) {
        fprintf(stderr, "[%d] open: %s\n", idx, strerror(errno));
        return 1;
    }
    void *buf;
    if (posix_memalign(&buf, 4096, BS) != 0)
        return 1;
    off_t base = (off_t)idx * blocks * BS;
    for (long i = 0; i < blocks; ++i) {
        ssize_t r = pread(fd, buf, BS, base + (off_t)i * BS);
        if (r != BS) {
            fprintf(stderr, "[%d] pread: %s\n", idx, r < 0 ? strerror(errno) : "short read");
            return 1;
        }
    }
    free(buf);
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <device|file> [nproc=8] [blocks=400]\n", argv[0]);
        return 2;
    }
    int nproc = argc > 2 ? atoi(argv[2]) : 8;
    long blocks = argc > 3 ? atol(argv[3]) : 400;
    if (nproc <= 0 || blocks <= 0)
        return 2;

    double t0 = now_ms();
    for (int i = 0; i < nproc; ++i) {
        pid_t pid = fork();
        if (pid < 0) {
            perror("fork");
            return 1;
        }
        if (pid == 0)
            _exit(reader(argv[1], i, blocks));
    }
    int failed = 0, status;
    while (wait(&status) > 0)
        if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
            failed = 1;
    double t1 = now_ms();

    double mib = (double)nproc * blocks * BS / (1024.0 * 1024.0);
    printf("nproc=%d blocks=%ld total=%.0f MiB time_ms=%.1f throughput=%.1f MiB/s%s\n",
           nproc, blocks, mib, t1 - t0, mib / ((t1 - t0) / 1e3), failed ? " (ошибки!)" : "");
    return failed;
}
