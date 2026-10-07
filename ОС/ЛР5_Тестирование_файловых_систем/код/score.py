#!/usr/bin/env python3
"""Интегральная оценка файловых систем (раздел 1.8 отчёта ЛР5).

Для каждой метрики значение ФС делится на максимум среди всех ФС
(1,000 = лучший результат), итог S — среднее пяти нормированных метрик с
равными весами: последовательная запись, случайное чтение, случайная
запись, создание и удаление файлов. Последовательное чтение в S не входит
из-за нестабильности на loop/WSL2.

Вход: CSV в формате fs_bench.sh (по строке на прогон — значения
усредняются по ФС) или уже усреднённая сводка ../данные/fs_summary_*.csv.
    python3 score.py                       # данные отчёта
    python3 score.py fs_bench_XXXX.csv     # свой прогон
    python3 score.py --plot                # + рисунки 1 и 2 (нужен matplotlib)
"""
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "данные" / "fs_summary_2026-10-02.csv"
METRICS = [
    ("seq_write_mibs", "Посл. запись"),
    ("rand_read_iops", "Случ. чтение"),
    ("rand_write_iops", "Случ. запись"),
    ("create_fps", "Создание"),
    ("delete_fps", "Удаление"),
]
NAMES = {"ext4": "ext4", "xfs": "XFS", "btrfs": "btrfs", "f2fs": "F2FS"}


def load(path):
    acc = defaultdict(lambda: defaultdict(list))
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key, val in row.items():
                if key not in ("fs", "run") and val not in ("", None):
                    acc[row["fs"]][key].append(float(val))
    return {fs: {k: statistics.mean(v) for k, v in m.items()} for fs, m in acc.items()}


def score(data):
    best = {m: max(d[m] for d in data.values()) for m, _ in METRICS}
    table = {}
    for fs, d in data.items():
        norm = [d[m] / best[m] for m, _ in METRICS]
        table[fs] = (norm, sum(norm) / len(norm))
    return table


def plot(data, table, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fss = list(data)
    labels = [NAMES.get(f, f) for f in fss]
    x = range(len(fss))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [data[f]["create_fps"] for f in fss], w, label="Создание")
    ax.bar([i + w / 2 for i in x], [data[f]["delete_fps"] for f in fss], w, label="Удаление")
    ax.set_xticks(list(x), labels)
    ax.set_ylabel("файл/с")
    ax.set_title("Скорость создания и удаления 4000 файлов")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(outdir / "fig1_metadata.png", dpi=150)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    s = [table[f][1] for f in fss]
    bars = ax.bar(labels, s, color="tab:green")
    ax.bar_label(bars, [f"{v:.3f}" for v in s])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("S")
    ax.set_title("Интегральная оценка файловых систем")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(outdir / "fig2_score.png", dpi=150)
    print(f"рисунки сохранены в {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default=DEFAULT)
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    data = load(args.csv)
    table = score(data)
    head = f"{'ФС':8s}" + "".join(f"{t:>14s}" for _, t in METRICS) + f"{'S':>9s}"
    print(head)
    for fs, (norm, s) in sorted(table.items(), key=lambda kv: -kv[1][1]):
        print(f"{NAMES.get(fs, fs):8s}" + "".join(f"{v:14.3f}" for v in norm) + f"{s:9.3f}")
    winner = max(table, key=lambda f: table[f][1])
    seq_best = max(data, key=lambda f: data[f]["seq_write_mibs"])
    print(f"\nЛучшая по интегральной оценке: {NAMES.get(winner, winner)} "
          f"(S = {table[winner][1]:.3f})")
    print(f"Лучшая по последовательной записи: {NAMES.get(seq_best, seq_best)} "
          f"({data[seq_best]['seq_write_mibs']:.0f} МиБ/с)")
    if args.plot:
        plot(data, table, Path(args.outdir))


if __name__ == "__main__":
    main()
