#!/bin/bash
# Усиленный вариант (раздел 2 отчёта): у работающего Kyber меняется целевая
# задержка чтения 2 мс -> 1 мс -> 2 мс через read_lat_nsec, на каждой цели
# выполняется hdparm -tT. В ядре запись в этот файл обрабатывает
# kyber_read_lat_store(), который пишет kqd->latency_targets[KYBER_READ].
set -u

DISC="${1:-sdd}"
PAUSE="${PAUSE:-15}"
Q="/sys/block/$DISC/queue"

[[ $EUID -eq 0 ]] || { echo "нужны права root" >&2; exit 1; }

echo kyber > "$Q/scheduler"
echo "scheduler: $(cat "$Q/scheduler")"
echo "read_lat_nsec  = $(cat "$Q/iosched/read_lat_nsec")"   # ожидается 2000000
echo "write_lat_nsec = $(cat "$Q/iosched/write_lat_nsec")"  # ожидается 10000000

for target in 2000000 1000000 2000000; do
    echo "$target" > "$Q/iosched/read_lat_nsec"
    got=$(cat "$Q/iosched/read_lat_nsec")
    if [[ $got != "$target" ]]; then
        echo "ядро не приняло значение: $got" >&2; exit 1
    fi
    sync
    disk=$(/sbin/hdparm -t "/dev/$DISC" | awk '/buffered/ {print $(NF-1)}')
    printf 'target=%s ns (%s ms)\tdisk=%s MB/s\n' "$target" "$((target / 1000000))" "$disk"
    sleep "$PAUSE"
done

# вернуть исходное состояние
echo 2000000 > "$Q/iosched/read_lat_nsec"
echo none > "$Q/scheduler"
