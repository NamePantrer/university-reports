#!/bin/bash
# Контрольная серия (раздел 1.5 отчёта): два прогревочных hdparm -t,
# затем три круга hdparm -tT с разным порядком планировщиков, чтобы
# прогрев кэша виртуального диска не доставался всегда одному планировщику.
# Результат дописывается в CSV: round,scheduler,cached_mbs,disk_mbs
# Для серии с mq-deadline (раздел 1.6): SERIES=mq ./control_series.sh sdd
set -u

DISC="${1:-sdd}"
PAUSE="${PAUSE:-8}"
OUT="${OUT:-control_series_$(date +%Y%m%d_%H%M%S).csv}"
SERIES="${SERIES:-base}"

[[ $EUID -eq 0 ]] || { echo "нужны права root" >&2; exit 1; }
modprobe bfq 2>/dev/null || true

if [[ $SERIES == mq ]]; then
    # четыре круга со сдвигом: каждый планировщик бывает и первым, и последним
    ROUNDS=("kyber bfq none mq-deadline"
            "bfq none mq-deadline kyber"
            "none mq-deadline kyber bfq"
            "mq-deadline kyber bfq none")
else
    ROUNDS=("kyber bfq none" "none kyber bfq" "bfq none kyber")
fi

# hdparm печатает строки вида "... = 3468.11 MB/sec"; берём последнее число
measure() {
    local out cached disk
    out=$(/sbin/hdparm -tT "/dev/$DISC")
    cached=$(awk '/cached reads/ {print $(NF-1)}' <<<"$out")
    disk=$(awk '/buffered disk reads/ {print $(NF-1)}' <<<"$out")
    echo "$cached,$disk"
}

echo "прогрев:" >&2
for w in 1 2; do
    echo "  warmup $w: $(/sbin/hdparm -t "/dev/$DISC" | awk '/buffered/ {print $(NF-1), $NF}')" >&2
done

echo "round,scheduler,cached_mbs,disk_mbs" > "$OUT"
r=0
for order in "${ROUNDS[@]}"; do
    r=$((r + 1))
    for T in $order; do
        echo "$T" > "/sys/block/$DISC/queue/scheduler"
        grep -q "\[$T\]" "/sys/block/$DISC/queue/scheduler" || { echo "не включился $T" >&2; exit 1; }
        sync
        res=$(measure)
        echo "$r,$T,$res" | tee -a "$OUT"
        sleep "$PAUSE"
    done
done
echo none > "/sys/block/$DISC/queue/scheduler"
echo "результаты: $OUT" >&2
