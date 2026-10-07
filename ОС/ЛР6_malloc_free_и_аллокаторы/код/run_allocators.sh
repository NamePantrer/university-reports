#!/usr/bin/env bash
# Приложение Б отчёта ЛР6: собирает один бинарный файл malloc_bench,
# запускает его с glibc и с jemalloc / mimalloc / tcmalloc через LD_PRELOAD,
# затем строит графики (plot_compare.py).
# Debian/Ubuntu: sudo apt install libjemalloc2 libmimalloc3 libtcmalloc-minimal4t64
#   (в Ubuntu 24.04 и старше пакеты могут называться libmimalloc2.0 / libtcmalloc-minimal4)
set -euo pipefail

CC=${CC:-gcc}
CFLAGS=${CFLAGS:--O2 -std=c11 -Wall -Wextra}

$CC $CFLAGS -o malloc_bench malloc_bench.c

find_so() {
    local pattern="$1"
    ldconfig -p | awk -v p="$pattern" '$1 ~ p { print $NF; exit }'
}

run_one() {
    local name="$1"
    local so="${2:-}"
    echo "Running ${name}..." >&2
    if [[ -n "$so" ]]; then
         ALLOCATOR_NAME="$name" LD_PRELOAD="$so" \
             ./malloc_bench > "${name}.csv"
    else
         ALLOCATOR_NAME="$name" ./malloc_bench > "${name}.csv"
    fi
}

JEMALLOC=$(find_so '^libjemalloc\.so')
MIMALLOC=$(find_so '^libmimalloc\.so')
TCMALLOC=$(find_so '^libtcmalloc(_minimal)?\.so')

[[ -n "$JEMALLOC" ]] || { echo "jemalloc not found" >&2; exit 1; }
[[ -n "$MIMALLOC" ]] || { echo "mimalloc not found" >&2; exit 1; }
[[ -n "$TCMALLOC" ]] || { echo "tcmalloc not found" >&2; exit 1; }

run_one glibc
run_one jemalloc "$JEMALLOC"
run_one mimalloc "$MIMALLOC"
run_one tcmalloc "$TCMALLOC"

python3 plot_compare.py
