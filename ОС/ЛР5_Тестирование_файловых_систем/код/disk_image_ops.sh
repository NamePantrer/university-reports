#!/bin/bash
# Раздел 1.2 отчёта: базовые операции с образами дисков перед сравнением ФС.
#  1) образ NTFS 64 МиБ, монтирование через ntfs-3g, проверка сохранения файла;
#  2) loop-устройство: losetup -f --show / -l / -d;
#  3) таблица разделов (fdisk/sfdisk) на образе 128 МиБ, kpartx, ext4 + XFS;
#  4) LVM из двух образов по 256 МиБ: pvcreate, vgcreate -s 32M, lvcreate,
#     pvmove, lvresize до 96 МиБ, удаление конфигурации.
# Всё делается в отдельном рабочем каталоге на файлах-образах — разметка
# реальных дисков не затрагивается. Запуск от root.
set -euo pipefail

WORK="${WORK:-$(mktemp -d /tmp/lab5.XXXX)}"
cd "$WORK"
echo "рабочий каталог: $WORK"
[[ $EUID -eq 0 ]] || { echo "нужны права root" >&2; exit 1; }

step() { printf '\n=== %s\n' "$*"; }

# ---------------------------------------------------------------- 1. NTFS
step "1. Образ NTFS"
mkdir -p mymount
dd if=/dev/zero of=123.bin bs=1M count=64 status=none
mkfs -t ntfs -F -Q 123.bin >/dev/null
if ! mount -o loop 123.bin mymount 2>/dev/null; then
    echo "ядро без ntfs3 — монтируем через ntfs-3g (FUSE)"
    mount -t ntfs-3g -o loop 123.bin mymount
fi
echo dfg > mymount/123.txt
umount mymount
mount -t ntfs-3g -o loop 123.bin mymount
echo "после повторного монтирования: $(cat mymount/123.txt)"
umount mymount

# ---------------------------------------------------------------- 2. loop
step "2. loop-устройство"
dd if=/dev/zero of=disk.img bs=1M count=32 status=none
LOOP=$(losetup -f --show disk.img)
losetup -l | grep "$LOOP"
losetup -d "$LOOP"

# ---------------------------------------------------------------- 3. разделы
step "3. Таблица разделов и kpartx"
dd if=/dev/zero of=parts.bin bs=1M count=128 status=none
# два первичных раздела Linux: 60 МиБ и всё оставшееся (~67 МиБ)
sfdisk --quiet parts.bin <<'PT'
label: dos
,60MiB,83
,,83
PT
LOOP=$(losetup -f --show parts.bin)
MAPS=$(kpartx -av "$LOOP" | awk '{print $3}')
echo "созданы отображения: $MAPS"
P1=/dev/mapper/$(sed -n 1p <<<"$MAPS"); P2=/dev/mapper/$(sed -n 2p <<<"$MAPS")
mkfs.ext4 -q -F "$P1"
mkfs.xfs -q -f "$P2"
mkdir -p p1 p2
mount "$P1" p1 && mount "$P2" p2
echo "ext4 ok" > p1/check.txt && echo "xfs ok" > p2/check.txt
cat p1/check.txt p2/check.txt
umount p1 p2
kpartx -d "$LOOP"
losetup -d "$LOOP"

# ---------------------------------------------------------------- 4. LVM
step "4. LVM"
dd if=/dev/zero of=pv0.img bs=1M count=256 status=none
dd if=/dev/zero of=pv1.img bs=1M count=256 status=none
L0=$(losetup -f --show pv0.img); L1=$(losetup -f --show pv1.img)
cleanup_lvm() {
    lvremove -y lab5vg/first >/dev/null 2>&1 || true
    vgremove -y lab5vg >/dev/null 2>&1 || true
    pvremove -y "$L0" "$L1" >/dev/null 2>&1 || true
    losetup -d "$L0" "$L1" 2>/dev/null || true
}
trap cleanup_lvm EXIT
pvcreate -ff -y "$L0" "$L1"
vgcreate -s 32M lab5vg "$L0" "$L1"
lvcreate -n first -L 64M lab5vg
mkfs.ext4 -q /dev/lab5vg/first
mkdir -p lv && mount /dev/lab5vg/first lv
echo "данные до pvmove" > lv/check.txt
pvs -o pv_name,pv_pe_count,pv_pe_alloc_count
pvmove "$L0" "$L1"              # перенос экстентов с первого PV на второй
lvresize -r -L 96M lab5vg/first # увеличение тома вместе с ФС
pvs -o pv_name,pv_pe_count,pv_pe_alloc_count
echo "после pvmove/lvresize: $(cat lv/check.txt), размер: $(df -h --output=size lv | tail -1)"
umount lv
cleanup_lvm
trap - EXIT
echo "готово"
