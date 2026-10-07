#!/usr/bin/env python3
# Приложение В отчёта ЛР6: читает четыре CSV и строит два сравнительных
# графика (рисунки 1 и 2 отчёта) в логарифмических шкалах.
import pandas as pd
import matplotlib.pyplot as plt

FILES = {
    "glibc": "glibc.csv",
    "jemalloc": "jemalloc.csv",
    "mimalloc": "mimalloc.csv",
    "tcmalloc": "tcmalloc.csv",
}

SERIES = [
    (
        "malloc_median_ns",
        "Allocator comparison — malloc_median_ns",
        "compare_malloc_median_ns.png",
    ),
    (
        "touch_median_ns",
        "Allocator comparison — touch_median_ns",
        "compare_touch_median_ns.png",
    ),
]

def load(path):
    return pd.read_csv(path, comment="#")

frames = {name: load(path) for name, path in FILES.items()}

for metric, title, output in SERIES:
    plt.figure(figsize=(10, 6))
    for name, df in frames.items():
        plt.plot(
            df["size_bytes"],
            df[metric],
            marker="o",
            markersize=2.5,
            linewidth=1.3,
            label=name,
        )

    plt.xscale("log", base=2)
    plt.yscale("log")
    plt.xlabel("Requested size (bytes)")
    plt.ylabel("Time (ns)")
    plt.title(title)
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
