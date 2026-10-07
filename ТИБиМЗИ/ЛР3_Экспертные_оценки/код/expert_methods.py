#!/usr/bin/env python3
"""Методы экспертных оценок из ЛР3 (только стандартная библиотека).

1. Непосредственная оценка: средние баллы, выборочное СКО, коэффициент
   вариации V = sigma / mean * 100 % (согласовано при V < 33 %),
   интегральная оценка I = sum(w_i * mean_i).
2. Ранжирование: суммы рангов, коэффициент конкордации Кендалла
   W = 12 S / (m^2 (n^3 - n)), значимость chi2 = m (n - 1) W, df = n - 1.
3. Метод анализа иерархий (Саати): веса — нормированный главный собственный
   вектор матрицы парных сравнений (степенной метод), lambda_max,
   ИС = (lambda_max - n) / (n - 1), ОС = ИС / СИ (приемлемо при ОС < 0,10).

    python3 expert_methods.py              # данные отчёта из ../данные
    python3 expert_methods.py --data DIR   # свои CSV в том же формате
"""
import argparse
import csv
import math
import statistics
from fractions import Fraction
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "данные"
# критические значения chi2 при alpha = 0,05
CHI2_005 = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07, 6: 12.59, 7: 14.07, 8: 15.51, 9: 16.92, 10: 18.31}
# случайный индекс согласованности Саати
RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def read_table(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0][1:], [(r[0], r[1:]) for r in rows[1:]]


# ------------------------------------------------------------- метод 1
def direct_estimation(scores, weights):
    """scores: {вопрос: [баллы экспертов]}, weights: {вопрос: вес}"""
    if abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError("сумма весов должна быть 1")
    stats = {}
    for q, vals in scores.items():
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals)          # выборочное СКО (n - 1)
        stats[q] = (mean, sd, sd / mean * 100)
    integral = sum(weights[q] * stats[q][0] for q in scores)
    return stats, integral


# ------------------------------------------------------------- метод 2
def kendall_w(ranks):
    """ranks: список строк экспертов, в каждой ранги n объектов (без связок)."""
    m, n = len(ranks), len(ranks[0])
    sums = [sum(r[j] for r in ranks) for j in range(n)]
    mean = sum(sums) / n
    s = sum((x - mean) ** 2 for x in sums)
    w = 12 * s / (m ** 2 * (n ** 3 - n))
    chi2 = m * (n - 1) * w
    return sums, s, w, chi2, n - 1


# ------------------------------------------------------------- метод 3
def ahp(matrix, iters=1000, eps=1e-12):
    n = len(matrix)
    v = [1.0 / n] * n
    for _ in range(iters):
        nv = [sum(matrix[i][j] * v[j] for j in range(n)) for i in range(n)]
        s = sum(nv)
        nv = [x / s for x in nv]
        if max(abs(a - b) for a, b in zip(nv, v)) < eps:
            v = nv
            break
        v = nv
    av = [sum(matrix[i][j] * v[j] for j in range(n)) for i in range(n)]
    lam = sum(av[i] / v[i] for i in range(n)) / n
    ci = (lam - n) / (n - 1)
    cr = ci / RI[n] if RI[n] else 0.0
    return v, lam, ci, cr


def check_reciprocal(matrix):
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            if not math.isclose(matrix[i][j] * matrix[j][i], 1.0, rel_tol=1e-9):
                raise ValueError(f"матрица не обратно-симметрична в ({i + 1},{j + 1})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA)
    d = ap.parse_args().data

    # --- задача 1
    questions, rows = read_table(d / "task1_direct_scores.csv")
    scores = {q: [float(r[1][k]) for r in rows] for k, q in enumerate(questions)}
    with open(d / "task1_weights.csv", encoding="utf-8") as f:
        weights = {r["question"]: float(r["weight"]) for r in csv.DictReader(f)}
    stats, integral = direct_estimation(scores, weights)
    print("Задача 1. Метод непосредственной оценки")
    print(f"  {'':6s}" + "".join(f"{q:>8s}" for q in questions))
    for label, idx, fmt in (("x̄", 0, "{:8.1f}"), ("σ", 1, "{:8.2f}"), ("V, %", 2, "{:8.1f}")):
        print(f"  {label:6s}" + "".join(fmt.format(stats[q][idx]) for q in questions))
    vmax = max(s[2] for s in stats.values())
    contrib = sorted(((weights[q] * stats[q][0], q) for q in questions), reverse=True)
    print(f"  I = {' + '.join(f'{weights[q]:.2f}·{stats[q][0]:.1f}' for q in questions)} = {integral:.2f} из 10")
    print(f"  max V = {vmax:.1f} % {'< 33 % -> мнения согласованы' if vmax < 33 else '>= 33 % -> НЕ согласованы'}")
    print(f"  наибольшие взвешенные вклады: {contrib[0][1]} ({contrib[0][0]:.2f}), {contrib[1][1]} ({contrib[1][0]:.2f})")

    # --- задача 2
    objects, rows = read_table(d / "task2_ranks.csv")
    ranks = [[int(x) for x in r[1]] for r in rows]
    sums, s, w, chi2, df = kendall_w(ranks)
    print("\nЗадача 2. Метод ранжирования")
    print("  суммы рангов: " + ", ".join(f"{o}={x}" for o, x in zip(objects, sums)))
    print(f"  S = {s:.0f};  W = {w:.3f};  chi2 = {chi2:.2f};  chi2кр(0,05; df={df}) = {CHI2_005[df]}")
    print(f"  {'согласованность статистически значима' if chi2 > CHI2_005[df] else 'согласованность НЕ значима'}")
    order = [o for _, o in sorted(zip(sums, objects))]
    print("  приоритет: " + " -> ".join(order))

    # --- задача 3
    crit, rows = read_table(d / "task3_pairwise.csv")
    matrix = [[float(Fraction(x)) for x in r[1]] for r in rows]
    check_reciprocal(matrix)
    v, lam, ci, cr = ahp(matrix)
    print("\nЗадача 3. Метод анализа иерархий")
    print("  веса: " + "; ".join(f"{c} = {x:.3f}" for c, x in zip(crit, v)) + f" (сумма {sum(v):.3f})")
    print(f"  λmax = {lam:.3f};  ИС = {ci:.3f};  ОС = {cr:.3f} "
          f"{'< 0,10 -> суждения согласованы' if cr < 0.10 else '>= 0,10 -> пересмотреть матрицу'}")


if __name__ == "__main__":
    main()
