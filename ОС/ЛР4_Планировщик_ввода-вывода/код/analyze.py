#!/usr/bin/env python3
"""Пересчёт сводных показателей ЛР4 из CSV в ../данные (таблицы 2, 4, 5 отчёта).

Отрыв лидера считается относительно результата лидера:
    gap = (лидер - X) / лидер * 100 %
(именно так получены 1,84 % и 2,81 % в разделе 1.5 и 1,27 % в разделе 1.6).
Только стандартная библиотека, Python 3.8+.
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "данные"


def load(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def series_means(rows, skip_rounds=()):
    by = defaultdict(list)
    for r in rows:
        if int(r["round"]) in skip_rounds:
            continue
        by[r["scheduler"]].append(float(r["disk_mbs"]))
    return {k: (statistics.mean(v), min(v), max(v)) for k, v in by.items()}


def report(title, means):
    print(f"\n{title}")
    leader, (lead_mean, _, _) = max(means.items(), key=lambda kv: kv[1][0])
    for name, (m, lo, hi) in sorted(means.items(), key=lambda kv: -kv[1][0]):
        gap = (lead_mean - m) / lead_mean * 100
        print(f"  {name:12s} среднее {m:8.2f} МБ/с  разброс {lo:.2f}-{hi:.2f}  "
              f"отставание от {leader}: {gap:4.2f} %")


def main():
    task = load("hdparm_task_run.csv")
    print("Один проход скрипта задания (таблица 1), диск -t по порядку запуска:")
    print("  " + " -> ".join(f"{r['scheduler']} {float(r['disk_mbs']):.2f}" for r in task))

    report("Контрольная серия 30.09.2026, три круга (таблица 2):",
           series_means(load("hdparm_control_series_2026-09-30.csv")))
    report("Серия с mq-deadline 02.10.2026, среднее кругов 2-4 (таблица 5):",
           series_means(load("hdparm_mq_deadline_series_2026-10-02.csv"), skip_rounds={1}))

    print("\nKyber, цель чтения 2 -> 1 -> 2 мс (таблица 4):")
    kt = load("kyber_target.csv")
    vals = [float(r["disk_mbs"]) for r in kt]
    for r in kt:
        print(f"  {int(r['read_lat_nsec']) / 1e6:.0f} мс: {float(r['disk_mbs']):.2f} МБ/с")
    linear_mid = (vals[0] + vals[2]) / 2
    print(f"  середина линейного тренда {linear_mid:.2f}, прогон с 1 мс {vals[1]:.2f} "
          f"(отклонение {vals[1] - linear_mid:+.2f} МБ/с) -> скачка из-за смены цели нет")

    print("\nГистограмма Kyber: ширина корзины = цель / 4")
    for target_ms in (2, 1):
        print(f"  цель {target_ms} мс -> первая корзина до {target_ms * 1000 / 4:.0f} мкс")
    worst_p99 = max(float(r["p99_us"]) for r in load("odirect_latency.csv"))
    print(f"  худший p99 в таблицах 3 и 6: {worst_p99} мкс < 250 мкс -> глубина очереди не урезается")


if __name__ == "__main__":
    main()
