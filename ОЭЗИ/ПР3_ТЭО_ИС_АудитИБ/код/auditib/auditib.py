#!/usr/bin/env python3
"""Прототип ИС «АудитИБ» (функции очереди 1 из ТЭО, ПР3 ОЭЗИ).

Реестр объектов, чек-листы, календарь аудитов, журнал несоответствий с
владельцем и сроком, KPI «доля закрытых в срок», отчёт по аудиту
(Markdown; в целевой системе — PDF), журнал действий пользователей.
Хранилище — SQLite (в целевой системе — СУБД на VPS в РФ).

    python3 auditib.py demo                    # создать демо-БД и показать отчёт
    python3 auditib.py --db a.db init
    python3 auditib.py --db a.db report 1 > audit1.md
    python3 auditib.py --db a.db kpi
    python3 auditib.py --db a.db close 3 --on 2026-09-10 --user 1
"""
import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init(con):
    con.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
    con.commit()


def log(con, user_id, action, details=""):
    con.execute("INSERT INTO action_log(user_id, action, details) VALUES (?,?,?)", (user_id, action, details))


def add(con, table, user_id=None, **fields):
    cols = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    cur = con.execute(f"INSERT INTO {table}({cols}) VALUES ({marks})", tuple(fields.values()))
    log(con, user_id, f"create {table}", f"id={cur.lastrowid}")
    return cur.lastrowid


def record_answer(con, audit_id, item_id, result, comment, user_id, owner_id=None, due_days=30):
    """Ответ на пункт чек-листа; «нет» автоматически порождает несоответствие."""
    con.execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?)", (audit_id, item_id, result, comment))
    if result == "нет":
        if owner_id is None:
            raise ValueError("для несоответствия нужен владелец (регламент, п. 5.3)")
        done = con.execute("SELECT COALESCE(done_on, planned_on) d FROM audits WHERE id=?", (audit_id,)).fetchone()["d"]
        crit = con.execute("SELECT critical FROM checklist_items WHERE id=?", (item_id,)).fetchone()["critical"]
        days = 7 if crit else due_days                      # критичные — неделя
        due = (dt.date.fromisoformat(done) + dt.timedelta(days=days)).isoformat()
        text = con.execute("SELECT text FROM checklist_items WHERE id=?", (item_id,)).fetchone()["text"]
        return add(con, "findings", user_id, audit_id=audit_id, item_id=item_id,
                   descr=f"Не выполнено «{text}»" + (f": {comment}" if comment else ""), owner_id=owner_id, due_on=due)
    return None


def close_finding(con, finding_id, on, user_id):
    n = con.execute("UPDATE findings SET status='закрыто', closed_on=? WHERE id=? AND status='открыто'",
                    (on, finding_id)).rowcount
    if not n:
        raise SystemExit(f"несоответствие {finding_id} не найдено или уже закрыто")
    log(con, user_id, "close finding", f"id={finding_id} on={on}")
    con.commit()


def kpi(con, today=None):
    today = today or dt.date.today().isoformat()
    r = con.execute("""
        SELECT COUNT(*) total,
               SUM(closed_on IS NOT NULL AND closed_on <= due_on) in_time,
               SUM(closed_on IS NULL AND due_on < ?) overdue
        FROM findings WHERE due_on <= ? OR closed_on IS NOT NULL""", (today, today)).fetchone()
    total, in_time, overdue = r["total"], r["in_time"] or 0, r["overdue"] or 0
    pct = 100.0 * in_time / total if total else 0.0
    return total, in_time, overdue, pct


def report(con, audit_id):
    a = con.execute("""SELECT a.*, s.name site, s.customer, c.name checklist, u.full_name auditor
                       FROM audits a JOIN sites s ON s.id=a.site_id JOIN checklists c ON c.id=a.checklist_id
                       JOIN users u ON u.id=a.auditor_id WHERE a.id=?""", (audit_id,)).fetchone()
    if a is None:
        raise SystemExit(f"аудит {audit_id} не найден")
    out = [f"# Отчёт по аудиту ИБ №{a['id']}", "",
           f"- Площадка: {a['site']} ({a['customer']})",
           f"- Чек-лист: {a['checklist']}",
           f"- Дата: {a['done_on'] or a['planned_on']} — статус: {a['status']}",
           f"- Аудитор: {a['auditor']}", ""]
    rows = con.execute("""SELECT i.code, i.text, i.critical, an.result, an.comment, i.course_module
                          FROM answers an JOIN checklist_items i ON i.id=an.item_id
                          WHERE an.audit_id=? ORDER BY i.code""", (audit_id,)).fetchall()
    yes = sum(r["result"] == "да" for r in rows)
    no = sum(r["result"] == "нет" for r in rows)
    out += [f"Проверено пунктов: {len(rows)}; выполнено: {yes}; несоответствий: {no}", "",
            "| Пункт | Требование | Результат | Комментарий | Модуль курса |", "|---|---|---|---|---|"]
    for r in rows:
        mark = " ⚠" if r["critical"] and r["result"] == "нет" else ""
        out.append(f"| {r['code']} | {r['text']} | {r['result']}{mark} | {r['comment'] or ''} | "
                   f"{r['course_module'] or ''} |")
    out += ["", "## Несоответствия", "", "| № | Описание | Владелец | Срок | Статус |", "|---|---|---|---|---|"]
    for f in con.execute("""SELECT f.*, u.full_name owner FROM findings f JOIN users u ON u.id=f.owner_id
                            WHERE audit_id=? ORDER BY f.due_on""", (audit_id,)):
        st = f["status"] + (f" {f['closed_on']}" if f["closed_on"] else "")
        out.append(f"| {f['id']} | {f['descr']} | {f['owner']} | {f['due_on']} | {st} |")
    return "\n".join(out) + "\n"


def demo(path):
    p = Path(path)
    if p.exists():
        p.unlink()
    con = connect(path)
    init(con)
    eng = add(con, "users", None, login="ivanov", full_name="Иванов И. (инженер ИБ)", role="engineer")
    mst = add(con, "users", eng, login="petrov", full_name="Петров П. (мастер участка)", role="master")
    add(con, "users", eng, login="sidorova", full_name="Сидорова С. (нач. производства)", role="head")
    site = add(con, "sites", eng, name="Сборочный участок", customer="ООО «СеверМодуль»", address="Санкт-Петербург")
    add(con, "audit_objects", eng, site_id=site, kind="ПЛК", name="Линия прошивки контроллеров, ПЛК-1")
    add(con, "audit_objects", eng, site_id=site, kind="сеть", name="Wi-Fi цеха")
    cl = add(con, "checklists", eng, name="Обход цеха по ИБ (курс, модуль 2)")
    items = [("2.1", "Пароли по умолчанию на ПЛК и HMI сменены", 1, 3),
             ("2.5", "Удалённый доступ подрядчиков согласован", 0, 3),
             ("3.1", "Сеть цеха отделена от офисной", 0, 4),
             ("3.2", "Нет общего Wi-Fi для оборудования и смартфонов", 1, 4),
             ("4.1", "Есть актуальные копии проектов ПЛК и HMI", 1, 5),
             ("4.3", "Восстановление из копии проверялось за 12 месяцев", 1, 5),
             ("5.3", "Флешки наладчиков проверяются", 0, 6)]
    ids = {code: add(con, "checklist_items", eng, checklist_id=cl, code=code, text=t, critical=c, course_module=m)
           for code, t, c, m in items}
    audit = add(con, "audits", eng, site_id=site, checklist_id=cl, planned_on="2026-09-01",
                done_on="2026-09-01", auditor_id=eng, status="завершён")
    answers = [("2.1", "нет", "на ПЛК-1 заводской пароль"), ("2.5", "да", None), ("3.1", "да", None),
               ("3.2", "нет", "наладчики подключают ноутбуки к общему Wi-Fi"),
               ("4.1", "да", None), ("4.3", "нет", "проверка восстановления не проводилась"),
               ("5.3", "нет", "флешки не проверяются")]
    f = {code: record_answer(con, audit, ids[code], res, com, eng, owner_id=mst) for code, res, com in answers}
    con.commit()
    close_finding(con, f["2.1"], "2026-09-05", eng)   # в срок (критичное, 7 дней)
    close_finding(con, f["3.2"], "2026-09-12", eng)   # просрочено
    close_finding(con, f["5.3"], "2026-09-20", eng)   # в срок (30 дней)
    print(report(con, audit))
    total, in_time, overdue, pct = kpi(con, today="2026-10-08")
    print(f"KPI на 2026-10-08: закрыто в срок {in_time} из {total} ({pct:.0f} %), "
          f"просрочено открытых: {overdue}. Цель ТЭО: >= 85 %.")
    print(f"Записей в журнале действий: {con.execute('SELECT COUNT(*) FROM action_log').fetchone()[0]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="auditib.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    r = sub.add_parser("report"); r.add_argument("audit_id", type=int)
    sub.add_parser("kpi")
    c = sub.add_parser("close"); c.add_argument("finding_id", type=int)
    c.add_argument("--on", default=dt.date.today().isoformat()); c.add_argument("--user", type=int)
    a = ap.parse_args()
    if a.cmd == "demo":
        return demo(a.db)
    con = connect(a.db)
    if a.cmd == "init":
        init(con); print(f"БД создана: {a.db}")
    elif a.cmd == "report":
        sys.stdout.write(report(con, a.audit_id))
    elif a.cmd == "kpi":
        total, in_time, overdue, pct = kpi(con)
        print(f"закрыто в срок: {in_time}/{total} ({pct:.1f} %), просрочено открытых: {overdue}")
    elif a.cmd == "close":
        close_finding(con, a.finding_id, a.on, a.user)


if __name__ == "__main__":
    main()
