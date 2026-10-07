#!/usr/bin/env python3
"""Сводные таблицы 2-4 отчёта ЛР6 из CSV, полученных run_allocators.sh.

Для характерных размеров (16 Б, 4 КБ, 64 КБ, 1 МБ, 4 МБ) печатает медианы
malloc, malloc с касанием и free по всем аллокаторам, плюс отношение
glibc к самому быстрому. Только стандартная библиотека.
    python3 summary_table.py [--md]
"""
import csv
import sys
from pathlib import Path

ALLOCATORS = ["glibc", "jemalloc", "mimalloc", "tcmalloc"]
SIZES = [(16, "16 Б"), (4096, "4 КБ"), (65536, "64 КБ"), (1048576, "1 МБ"), (4194304, "4 МБ")]
METRICS = [
    ("malloc_median_ns", "Таблица 2 — медианное время malloc, нс"),
    ("touch_median_ns", "Таблица 3 — malloc с касанием памяти, нс"),
    ("free_median_ns", "Таблица 4 — медианное время free, нс"),
]


def load(name):
    rows = {}
    with open(f"{name}.csv", encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(lines):
        rows[int(r["size_bytes"])] = {k: int(v) for k, v in r.items()}
    return rows


def main():
    md = "--md" in sys.argv
    present = [a for a in ALLOCATORS if Path(f"{a}.csv").exists()]
    if not present:
        sys.exit("нет CSV: сначала запустите ./run_allocators.sh")
    data = {a: load(a) for a in present}
    for key, title in METRICS:
        print(f"\n{title}")
        head = ["Размер"] + present + ["glibc / лучший"]
        print("| " + " | ".join(head) + " |" if md else "  ".join(f"{h:>14s}" for h in head))
        if md:
            print("|" + "---|" * len(head))
        for size, label in SIZES:
            vals = [data[a][size][key] for a in present]
            best = max(min(vals), 1)
            ratio = f"{data['glibc'][size][key] / best:.1f}x" if "glibc" in data else "—"
            cells = [label] + [str(v) for v in vals] + [ratio]
            print("| " + " | ".join(cells) + " |" if md else "  ".join(f"{c:>14s}" for c in cells))


if __name__ == "__main__":
    main()
