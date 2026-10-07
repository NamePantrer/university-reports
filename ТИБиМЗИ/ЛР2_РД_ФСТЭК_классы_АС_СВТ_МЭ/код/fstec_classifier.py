#!/usr/bin/env python3
"""Подбор класса АС, минимальных классов СВТ и МЭ по РД Гостехкомиссии.

Реализует порядок решения из раздела 2 отчёта ЛР2:
  шаг 1 — правовой режим информации (гриф / конфиденциально / открыто);
  шаг 2 — кто работает в АС (один / несколько с равными / с разными правами);
  шаг 3 — группа и класс АС (РД «АС. Защита от НСД», 30.03.1992, п. 1.7-1.9, 2.18);
  шаг 4 — класс СВТ не ниже (п. 2.18 и привязка к грифу, таблица 3 отчёта);
  шаг 5 — класс МЭ не ниже (РД «МЭ», 25.07.1997, п. 1.5-1.6);
  шаги 6-7 — флаги 187-ФЗ (КИИ), ПДн и необходимость оценки угроз по
             Методике ФСТЭК от 05.02.2021.

    python3 fstec_classifier.py                    # все 7 кейсов -> сводная таблица 11
    python3 fstec_classifier.py --info СС --users equal
    python3 fstec_classifier.py --json             # то же в JSON
"""
import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# уровни информации: гостайна (ОВ, СС, С), конфиденциальная, открытая
STATE_SECRET = ("ОВ", "СС", "С")
LEVELS = STATE_SECRET + ("конф", "откр")

# Таблица 2 отчёта: (режим пользователей, уровень) -> класс АС
AS_TABLE = {
    "single": {"ОВ": "3А", "СС": "3А", "С": "3А", "конф": "3Б", "откр": "3Б"},
    "equal":  {"ОВ": "2А", "СС": "2А", "С": "2А", "конф": "2Б", "откр": "2Б"},
    "differ": {"ОВ": "1А", "СС": "1Б", "С": "1В", "конф": "1Г", "откр": "1Д"},
}
# Таблица 3 отчёта: класс АС -> (СВТ не ниже, МЭ не ниже); для 2А/3А — по грифу
SVT_ME = {"1А": (2, 1), "1Б": (3, 2), "1В": (4, 3), "1Г": (5, 4), "1Д": (6, 5),
          "2Б": (6, 5), "3Б": (6, 5)}
BY_GRIF = {"ОВ": (2, 1), "СС": (3, 2), "С": (4, 3)}
USERS_RU = {"single": "один пользователь", "equal": "несколько, права равные",
            "differ": "несколько, права разные"}


@dataclass
class Case:
    name: str
    info: str            # высший уровень информации из LEVELS
    users: str           # single / equal / differ
    info_note: str = ""
    kii: bool = False    # объект КИИ по 187-ФЗ
    pdn: bool = False    # персональные данные
    internet: bool = False
    notes: list = field(default_factory=list)


@dataclass
class Result:
    case: str
    info: str
    users: str
    as_class: str
    svt_min: int
    me_min: int
    group: int
    extra: list


def classify(c: Case) -> Result:
    if c.info not in LEVELS:
        raise ValueError(f"{c.name}: неизвестный уровень информации {c.info!r}")
    if c.users not in AS_TABLE:
        raise ValueError(f"{c.name}: users должен быть single/equal/differ")
    as_class = AS_TABLE[c.users][c.info]
    if as_class in SVT_ME:
        svt, me = SVT_ME[as_class]
    else:                      # 2А / 3А — по грифу
        svt, me = BY_GRIF[c.info]
    extra = []
    if c.info in STATE_SECRET:
        extra.append("гостайна: класс не ниже 3А/2А/1В-1А (п. 2.18), охрана и спецоборудование помещений")
    if c.kii:
        extra.append("187-ФЗ: категорирование объектов КИИ, требования ФСТЭК к значимым объектам, ГосСОПКА")
    if c.pdn:
        extra.append("ПДн: требования к ИСПДн (152-ФЗ, ПП № 1119, приказ ФСТЭК № 21)")
    if c.kii or c.pdn or c.internet:
        extra.append("оценка угроз по Методике ФСТЭК 05.02.2021 и выбор мер под актуальные угрозы")
    if c.internet:
        extra.append(f"стык с внешней сетью: МЭ не ниже {me} класса с регистрацией соединений")
    extra.extend(c.notes)
    return Result(c.name, c.info_note or c.info, USERS_RU[c.users], as_class, svt, me,
                  int(as_class[0]), extra)


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return [Case(**c) for c in json.load(f)]


def print_table(results):
    print(f"{'Кейс':44s} {'Информация':28s} {'Пользователи':26s} {'АС':>3s} {'СВТ':>4s} {'МЭ':>3s}")
    print("-" * 114)
    for r in results:
        print(f"{r.case[:44]:44s} {r.info[:28]:28s} {r.users[:26]:26s} "
              f"{r.as_class:>3s} {r.svt_min:>4d} {r.me_min:>3d}")
        for e in r.extra:
            print(f"{'':6s}- {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=Path(__file__).with_name("cases.json"))
    ap.add_argument("--info", choices=LEVELS, help="классифицировать одну АС")
    ap.add_argument("--users", choices=list(AS_TABLE))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.info or a.users:
        if not (a.info and a.users):
            sys.exit("нужны оба параметра: --info и --users")
        results = [classify(Case("ввод пользователя", a.info, a.users))]
    else:
        results = [classify(c) for c in load_cases(a.cases)]
    if a.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
