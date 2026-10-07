#!/usr/bin/env python3
"""Деловая игра-квест по ИБ на основе инцидента NotPetya (ЛР4).

Правила (раздел 1.1 отчёта):
  * на каждом из 5 этапов три варианта решения: 3 балла (максимум),
    2 (среднее), 0 (ошибка);
  * решение засчитывается, только если в команде есть роль с нужным
    функционалом; иначе команда тратит ход на «обучение»/привлечение роли
    и выбирает снова. На этап даётся turns_per_stage ходов: если они
    кончились — этап засчитывается в 0 баллов (ситуация развивается сама);
  * максимум 15 баллов, исход определяется таблицей 7 отчёта.

Запуск:
    python3 quest.py                               # интерактивно, все 5 ролей
    python3 quest.py --roles SOC,ADMIN             # неполная команда
    python3 quest.py --auto max|mid|min|random     # демонстрационный прогон
    python3 quest.py --choices 1,2,1,1,3           # заранее заданные решения
"""
import argparse
import json
import random
import sys
from pathlib import Path

SCENARIO = Path(__file__).with_name("scenario.json")


def load(path=SCENARIO):
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    validate(sc)
    return sc


def validate(sc):
    roles = set(sc["roles"])
    total_max = 0
    for st in sc["stages"]:
        pts = sorted(o["points"] for o in st["options"])
        if pts != [0, 2, 3]:
            raise ValueError(f"этап {st['id']}: ожидаются варианты на 3/2/0 баллов, есть {pts}")
        for o in st["options"]:
            unknown = set(o.get("roles_any", []) + o.get("roles_all", [])) - roles
            if unknown:
                raise ValueError(f"этап {st['id']}: неизвестные роли {unknown}")
        total_max += 3
    covered = set()
    for oc in sc["outcomes"]:
        covered |= set(range(oc["min"], oc["max"] + 1))
    if covered != set(range(0, total_max + 1)):
        raise ValueError("таблица исходов покрывает не все суммы баллов")


def allowed(option, team):
    if option.get("roles_all"):
        return set(option["roles_all"]) <= team
    if option.get("roles_any"):
        return bool(set(option["roles_any"]) & team)
    return True


def missing_roles(option, team):
    need = option.get("roles_all") or option.get("roles_any") or []
    if option.get("roles_all"):
        return [r for r in need if r not in team]
    return [] if set(need) & team else need[:1]


def outcome(sc, score):
    return next(o["text"] for o in sc["outcomes"] if o["min"] <= score <= o["max"])


def play(sc, team, chooser, out=print):
    total, log = 0, []
    turns = sc.get("turns_per_stage", 2)
    for st in sc["stages"]:
        out(f"\n=== Этап {st['id']} ({st['kind']}). {st['title']}")
        out(st["situation"])
        f = st["fstec"]
        out(f"  [Методика ФСТЭК] последствия: {f['consequences']}; объекты: {f['objects']}; способ: {f['method']}")
        opts = st["options"][:]
        for i, o in enumerate(opts, 1):
            need = o.get("roles_all") or o.get("roles_any") or []
            who = (" + " if o.get("roles_all") else " / ").join(sc["roles"][r]["title"] for r in need) or "любая роль"
            out(f"  {i}) {o['text']}  [{who}]")
        got = 0
        for turn in range(1, turns + 1):
            k = chooser(st, opts, team)
            o = opts[k - 1]
            if allowed(o, team):
                got = o["points"]
                out(f"  -> выбран вариант {k}: {o['result']} (+{got})")
                break
            miss = missing_roles(o, team)
            out(f"  -> в команде нет роли: {', '.join(sc['roles'][r]['title'] for r in miss)}. "
                f"Ход {turn}/{turns} потрачен на обучение/привлечение.")
            team |= set(miss)
        else:
            out("  -> ходы на этапе закончились, ситуация развивается без вас (+0)")
        total += got
        log.append((st["id"], got))
    out(f"\nИтого: {total} из {3 * len(sc['stages'])} баллов")
    out(f"Исход: {outcome(sc, total)}")
    return total, log


def interactive_chooser(st, opts, team):
    while True:
        try:
            raw = input(f"  Ваше решение (1-{len(opts)}): ").strip()
        except EOFError:
            sys.exit("\nввод прерван")
        if raw.isdigit() and 1 <= int(raw) <= len(opts):
            return int(raw)
        print("  введите номер варианта")


def auto_chooser(mode, rng):
    target = {"max": 3, "mid": 2, "min": 0}

    def choose(st, opts, team):
        if mode == "random":
            return rng.randrange(len(opts)) + 1
        return next(i for i, o in enumerate(opts, 1) if o["points"] == target[mode])
    return choose


def list_chooser(seq):
    it = iter(seq)

    def choose(st, opts, team):
        try:
            return next(it)
        except StopIteration:
            sys.exit("в --choices не хватило решений")
    return choose


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=SCENARIO)
    ap.add_argument("--roles", help="роли команды через запятую (по умолчанию все)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--auto", choices=["max", "mid", "min", "random"])
    g.add_argument("--choices", help="номера решений по этапам, напр. 1,2,1,1,3")
    ap.add_argument("--seed", type=int, default=2017)
    a = ap.parse_args()

    sc = load(a.scenario)
    team = set(a.roles.split(",")) if a.roles else set(sc["roles"])
    if team - set(sc["roles"]):
        sys.exit(f"неизвестные роли: {team - set(sc['roles'])}; доступны {', '.join(sc['roles'])}")
    print(sc["title"])
    print(sc["based_on"])
    print("Команда: " + ", ".join(sc["roles"][r]["title"] for r in sc["roles"] if r in team))
    if a.auto:
        chooser = auto_chooser(a.auto, random.Random(a.seed))
    elif a.choices:
        chooser = list_chooser(int(x) for x in a.choices.split(","))
    else:
        chooser = interactive_chooser
    play(sc, team, chooser)


if __name__ == "__main__":
    main()
