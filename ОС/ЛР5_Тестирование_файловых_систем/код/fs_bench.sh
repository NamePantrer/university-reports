#!/bin/bash
# Сравнение файловых систем ext4, XFS, btrfs и F2FS на loop-образах (разделы
# 1.4-1.7 и приложение А отчёта).
# Для каждой ФС: новый образ 768 МиБ -> mkfs (время) -> mount -o loop ->
# прогрев 64 МиБ -> RUNS прогонов: последовательная запись/чтение 1 МиБ
# (256 МиБ, O_DIRECT, psync), случайное чтение/запись 4 КБ по 8 с,
# создание/удаление 4000 однобайтовых файлов. Между прогонами sync и сброс
# страничного кэша. Итог — CSV (по строке на прогон) для score.py.
# Зависимости: fio >= 3, jq, mkfs.{ext4,xfs,btrfs,f2fs}. Запуск от root.
set -euo pipefail

FS_LIST=${FS_LIST:-"ext4 xfs btrfs f2fs"}
RUNS=${RUNS:-2}
IMG_MB=${IMG_MB:-768}
NFILES=${NFILES:-4000}
WORK=${WORK:-/var/tmp/lab5_fs}
OUT=${OUT:-$PWD/fs_bench_$(date +%Y%m%d_%H%M%S).csv}

[[ $EUID -eq 0 ]] || { echo "нужны права root" >&2; exit 1; }
for c in fio jq; do command -v "$c" >/dev/null || { echo "нет $c" >&2; exit 1; }; done
mkdir -p "$WORK"; cd "$WORK"

mkfs_cmd() {
    case $1 in
        ext4)  echo "mkfs.ext4 -F -q" ;;
        xfs)   echo "mkfs.xfs -f -q" ;;
        btrfs) echo "mkfs.btrfs -f -q" ;;
        f2fs)  echo "mkfs.f2fs -f -q" ;;
        *) echo "неизвестная ФС $1" >&2; return 1 ;;
    esac
}

drop_caches() { sync; echo 3 > /proc/sys/vm/drop_caches; }

# fio -> МиБ/с (bw в JSON в КиБ/с) или IOPS
# первый аргумент — секция JSON (read/write), остальное — параметры fio
fio_bw()   { local d=$1; shift; fio --output-format=json "$@" | jq ".jobs[0].$d.bw / 1024"; }
fio_iops() { local d=$1; shift; fio --output-format=json "$@" | jq ".jobs[0].$d.iops | floor"; }
calc()     { awk "BEGIN { printf \"%.6f\", $1 }"; }

COMMON=(--filename=mnt/seq.bin --size=256M --direct=1 --ioengine=psync)

echo "fs,run,mkfs_s,seq_write_mibs,seq_read_mibs,rand_read_iops,rand_write_iops,create_fps,delete_fps" > "$OUT"

for fs in $FS_LIST; do
    echo "=== $fs" >&2
    rm -f "$fs.img"
    dd if=/dev/zero of="$fs.img" bs=1M count="$IMG_MB" status=none
    read -r -a MKFS <<<"$(mkfs_cmd "$fs")"
    t0=$(date +%s.%N); "${MKFS[@]}" "$fs.img"; t1=$(date +%s.%N)
    mkfs_s=$(calc "$t1 - $t0")
    mkdir -p mnt
    if ! mount -o loop "$fs.img" mnt; then
        echo "ядро не смонтировало $fs — пропуск" >&2
        rm -f "$fs.img"; continue
    fi
    dd if=/dev/zero of=mnt/warmup.bin bs=1M count=64 conv=fsync status=none
    rm -f mnt/warmup.bin

    for run in $(seq 1 "$RUNS"); do
        drop_caches
        sw=$(fio_bw write --name=seqw --rw=write --bs=1M "${COMMON[@]}" --end_fsync=1)
        drop_caches
        sr=$(fio_bw read --name=seqr --rw=read --bs=1M "${COMMON[@]}")
        drop_caches
        rr=$(fio_iops read --name=randr --rw=randread --bs=4k "${COMMON[@]}" --runtime=8 --time_based)
        drop_caches
        rw=$(fio_iops write --name=randw --rw=randwrite --bs=4k "${COMMON[@]}" --runtime=8 --time_based --end_fsync=1)

        drop_caches
        mkdir -p mnt/meta
        t0=$(date +%s.%N)
        for i in $(seq 1 "$NFILES"); do printf x > "mnt/meta/f$i"; done; sync
        t1=$(date +%s.%N)
        find mnt/meta -type f -delete; sync
        t2=$(date +%s.%N)
        cr=$(calc "$NFILES / ($t1 - $t0)")
        dl=$(calc "$NFILES / ($t2 - $t1)")

        printf '%s,%d,%.3f,%.0f,%.0f,%d,%d,%.0f,%.0f\n' \
            "$fs" "$run" "$mkfs_s" "$sw" "$sr" "$rr" "$rw" "$cr" "$dl" | tee -a "$OUT"
        rm -f mnt/seq.bin
    done
    sync; umount mnt
    rm -f "$fs.img"
done
echo "результаты: $OUT  (дальше: python3 score.py $OUT)" >&2
