#!/usr/bin/env python3
"""Калькулятор CVSS v3.0 / v3.1: базовая, временная и контекстная оценки.

Реализует формулы спецификаций FIRST CVSS v3.0 и v3.1 (раздел 7/8 спецификации).
Различия версий, влияющие на результат:
  * функция Roundup: в 3.0 — простое округление вверх до 0,1, в 3.1 —
    целочисленная версия, устойчивая к ошибкам двоичной арифметики;
  * ModifiedImpact при изменённой области (MS:C): в 3.1 добавлен множитель
    0,9731 и степень 13 вместо 15.

Использование:
    python3 cvss3.py "CVSS:3.0/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:L"
    python3 cvss3.py --lab           # три задачи из ЛР1 (г, д, в)
"""
import argparse
import math
import sys

W = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "CIA": {"H": 0.56, "L": 0.22, "N": 0.0},
    "E": {"X": 1.0, "H": 1.0, "F": 0.97, "P": 0.94, "U": 0.91},
    "RL": {"X": 1.0, "U": 1.0, "W": 0.97, "T": 0.96, "O": 0.95},
    "RC": {"X": 1.0, "C": 1.0, "R": 0.96, "U": 0.92},
    "REQ": {"X": 1.0, "H": 1.5, "M": 1.0, "L": 0.5},
}
PR_W = {"U": {"N": 0.85, "L": 0.62, "H": 0.27}, "C": {"N": 0.85, "L": 0.68, "H": 0.5}}

BASE_KEYS = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
NAMES = {
    "AV": "Вектор атаки", "AC": "Сложность атаки", "PR": "Привилегии",
    "UI": "Взаимодействие с пользователем", "S": "Область (Scope)",
    "C": "Конфиденциальность", "I": "Целостность", "A": "Доступность",
    "E": "Зрелость эксплойта", "RL": "Уровень исправления", "RC": "Достоверность отчёта",
    "CR": "Требование к К", "IR": "Требование к Ц", "AR": "Требование к Д",
}


def roundup30(x):
    return math.ceil(x * 10) / 10


def roundup31(x):
    i = int(round(x * 100000))
    if i % 10000 == 0:
        return i / 100000.0
    return (math.floor(i / 10000) + 1) / 10.0


def severity(score):
    if score == 0:
        return "None"
    if score < 4.0:
        return "Low"
    if score < 7.0:
        return "Medium"
    if score < 9.0:
        return "High"
    return "Critical"


def parse(vector):
    parts = vector.strip().split("/")
    version = "3.1"
    if parts[0].startswith("CVSS:"):
        version = parts.pop(0).split(":")[1]
    if version not in ("3.0", "3.1"):
        raise ValueError(f"поддерживаются только 3.0 и 3.1, получено {version}")
    m = {}
    for p in parts:
        k, v = p.split(":")
        m[k] = v
    missing = [k for k in BASE_KEYS if k not in m]
    if missing:
        raise ValueError(f"не хватает базовых метрик: {missing}")
    return version, m


def scores(vector):
    version, m = parse(vector)
    roundup = roundup30 if version == "3.0" else roundup31
    g = lambda k: m.get(k, "X")  # noqa: E731

    # ---------------- базовая оценка
    changed = m["S"] == "C"
    iss = 1 - (1 - W["CIA"][m["C"]]) * (1 - W["CIA"][m["I"]]) * (1 - W["CIA"][m["A"]])
    if changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    expl = 8.22 * W["AV"][m["AV"]] * W["AC"][m["AC"]] * PR_W[m["S"]][m["PR"]] * W["UI"][m["UI"]]
    if impact <= 0:
        base = 0.0
    elif changed:
        base = roundup(min(1.08 * (impact + expl), 10))
    else:
        base = roundup(min(impact + expl, 10))

    # ---------------- временная оценка
    tmult = W["E"][g("E")] * W["RL"][g("RL")] * W["RC"][g("RC")]
    temporal = roundup(base * tmult)

    # ---------------- контекстная оценка (Modified* = X -> берётся базовая метрика)
    mod = {k: (m.get("M" + k, "X") if m.get("M" + k, "X") != "X" else m[k]) for k in BASE_KEYS}
    mchanged = mod["S"] == "C"
    miss = min(1 - (1 - W["CIA"][mod["C"]] * W["REQ"][g("CR")])
                 * (1 - W["CIA"][mod["I"]] * W["REQ"][g("IR")])
                 * (1 - W["CIA"][mod["A"]] * W["REQ"][g("AR")]), 0.915)
    if mchanged:
        if version == "3.0":
            mimpact = 7.52 * (miss - 0.029) - 3.25 * (miss - 0.02) ** 15
        else:
            mimpact = 7.52 * (miss - 0.029) - 3.25 * (miss * 0.9731 - 0.02) ** 13
    else:
        mimpact = 6.42 * miss
    mexpl = (8.22 * W["AV"][mod["AV"]] * W["AC"][mod["AC"]]
             * PR_W[mod["S"]][mod["PR"]] * W["UI"][mod["UI"]])
    if mimpact <= 0:
        env = 0.0
    elif mchanged:
        env = roundup(roundup(min(1.08 * (mimpact + mexpl), 10)) * tmult)
    else:
        env = roundup(roundup(min(mimpact + mexpl, 10)) * tmult)

    return {
        "version": version, "base": base, "temporal": temporal, "environmental": env,
        "impact": impact, "exploitability": expl, "modified_impact": mimpact,
        "modified_exploitability": mexpl,
    }


# Задачи ЛР1. Калькулятор (как и онлайн-калькулятор FIRST) накопительный:
# временные метрики добавляются к базовому вектору задачи «г», контекстные —
# к нему же; MS:X («влияние на другие компоненты неизвестно») означает,
# что берётся базовая область S:C.
LAB = [
    ("г) базовые метрики",
     "AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:L", "base", 8.5),
    ("д) временные метрики: E:F (есть сценарий эксплуатации), "
     "RL:W (есть рекомендации по устранению), RC:C (источник подтверждён)",
     "AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:L/E:F/RL:W/RC:C", "temporal", 8.0),
    ("в) контекстные метрики: CR/IR/AR:H, MC/MI/MA:H, MAV:L, MAC:L, MPR:H, "
     "MUI:N, MS:X (неизвестно)",
     "AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:L/E:F/RL:W/RC:C/"
     "CR:H/IR:H/AR:H/MAV:L/MAC:L/MPR:H/MUI:N/MS:X/MC:H/MI:H/MA:H", "environmental", 7.8),
]


def run_lab():
    ok = True
    for title, vec, key, expected in LAB:
        print(f"\n{title}")
        for ver in ("3.0", "3.1"):
            s = scores(f"CVSS:{ver}/{vec}")
            mark = "  <- как в отчёте" if ver == "3.0" and s[key] == expected else ""
            print(f"  CVSS:{ver}  BS={s['base']:.1f}  TS={s['temporal']:.1f}  "
                  f"ES={s['environmental']:.1f}  ({severity(s[key])}){mark}")
            if ver == "3.0" and s[key] != expected:
                ok = False
                print(f"  !!! ожидалось {expected}")
        print(f"  вектор: CVSS:3.0/{vec}")
    print("\nВ отчёте использован калькулятор CVSS 3.0. Для задачи «в» версия 3.1 даёт 7.9:"
          "\nв 3.1 изменена формула ModifiedImpact при изменённой области.")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vector", nargs="?")
    ap.add_argument("--lab", action="store_true", help="пересчитать задачи ЛР1")
    a = ap.parse_args()
    if a.lab or not a.vector:
        sys.exit(0 if run_lab() else 1)
    s = scores(a.vector)
    for k in ("base", "temporal", "environmental"):
        print(f"{k:14s} {s[k]:4.1f}  {severity(s[k])}")
    print(f"impact={s['impact']:.3f} exploitability={s['exploitability']:.3f}")


if __name__ == "__main__":
    main()
