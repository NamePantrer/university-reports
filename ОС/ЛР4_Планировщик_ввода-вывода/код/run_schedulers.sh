#!/bin/bash
# Скрипт из приложения А отчёта: по очереди включает kyber, bfq и none
# на исследуемом блочном устройстве и запускает hdparm -tT.
# Запускать от root. Устройство можно передать первым аргументом (по умолчанию sdd).
set -u

DISC="${1:-sdd}"
PAUSE="${PAUSE:-15}"

[[ $EUID -eq 0 ]] || { echo "нужны права root" >&2; exit 1; }
[[ -e /sys/block/$DISC/queue/scheduler ]] || { echo "нет устройства /sys/block/$DISC" >&2; exit 1; }

modprobe bfq
sync
echo 3 > /proc/sys/vm/drop_caches

cat "/sys/block/$DISC/queue/scheduler"
for T in kyber bfq none; do
    echo "$T" > "/sys/block/$DISC/queue/scheduler"
    cat "/sys/block/$DISC/queue/scheduler"
    sync && /sbin/hdparm -tT "/dev/$DISC" && echo "----"
    sleep "$PAUSE"
done
