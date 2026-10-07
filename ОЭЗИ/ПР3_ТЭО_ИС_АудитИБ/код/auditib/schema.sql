-- ИС «АудитИБ», очередь 1 (MVP) — схема БД (SQLite / PostgreSQL-совместимый диалект).
-- Подсистемы из раздела 6.3 ТЭО: реестр объектов, чек-листы, журнал
-- несоответствий и задач, отчётность, администрирование пользователей.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS roles (
    code  TEXT PRIMARY KEY,                 -- engineer / master / head / customer
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id        INTEGER PRIMARY KEY,
    login     TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role      TEXT NOT NULL REFERENCES roles(code),
    active    INTEGER NOT NULL DEFAULT 1
);

-- реестр объектов аудита: площадки и зоны (цех, шкаф, ПЛК, СКУД ...)
CREATE TABLE IF NOT EXISTS sites (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    customer TEXT NOT NULL DEFAULT 'собственная площадка',
    address  TEXT
);

CREATE TABLE IF NOT EXISTS audit_objects (
    id      INTEGER PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES sites(id),
    kind    TEXT NOT NULL CHECK (kind IN ('зона цеха','шкаф','ПЛК','HMI','инженерная станция','сеть','СКУД','прочее')),
    name    TEXT NOT NULL
);

-- конструктор чек-листов; пункт может ссылаться на модуль курса (очередь 2)
CREATE TABLE IF NOT EXISTS checklists (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0'
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id           INTEGER PRIMARY KEY,
    checklist_id INTEGER NOT NULL REFERENCES checklists(id),
    code         TEXT NOT NULL,              -- 2.1, 3.2 ...
    text         TEXT NOT NULL,
    critical     INTEGER NOT NULL DEFAULT 0,
    course_module INTEGER,                   -- модуль курса «Аудит ИБ на малом производстве»
    UNIQUE (checklist_id, code)
);

-- календарь аудитов
CREATE TABLE IF NOT EXISTS audits (
    id           INTEGER PRIMARY KEY,
    site_id      INTEGER NOT NULL REFERENCES sites(id),
    checklist_id INTEGER NOT NULL REFERENCES checklists(id),
    planned_on   DATE NOT NULL,
    done_on      DATE,
    auditor_id   INTEGER NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'запланирован'
                 CHECK (status IN ('запланирован','в работе','завершён'))
);

CREATE TABLE IF NOT EXISTS answers (
    audit_id INTEGER NOT NULL REFERENCES audits(id),
    item_id  INTEGER NOT NULL REFERENCES checklist_items(id),
    result   TEXT NOT NULL CHECK (result IN ('да','нет','н/п')),
    comment  TEXT,
    PRIMARY KEY (audit_id, item_id)
);

-- журнал несоответствий и задач: владелец и срок обязательны
CREATE TABLE IF NOT EXISTS findings (
    id         INTEGER PRIMARY KEY,
    audit_id   INTEGER NOT NULL REFERENCES audits(id),
    item_id    INTEGER REFERENCES checklist_items(id),
    object_id  INTEGER REFERENCES audit_objects(id),
    descr      TEXT NOT NULL,
    owner_id   INTEGER NOT NULL REFERENCES users(id),   -- «владелец несоответствия»
    due_on     DATE NOT NULL,
    closed_on  DATE,
    status     TEXT NOT NULL DEFAULT 'открыто' CHECK (status IN ('открыто','закрыто'))
);

-- аудит действий пользователей (требование 4.2 ТЭО)
CREATE TABLE IF NOT EXISTS action_log (
    id      INTEGER PRIMARY KEY,
    at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    action  TEXT NOT NULL,
    details TEXT
);

-- KPI: доля несоответствий, закрытых в срок (цель ТЭО: с ~50 % до >= 85 %)
CREATE VIEW IF NOT EXISTS kpi_closed_in_time AS
SELECT
    COUNT(*)                                                         AS total_due,
    SUM(CASE WHEN closed_on IS NOT NULL AND closed_on <= due_on THEN 1 ELSE 0 END) AS closed_in_time,
    ROUND(100.0 * SUM(CASE WHEN closed_on IS NOT NULL AND closed_on <= due_on THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*), 0), 1)                                  AS pct_in_time
FROM findings
WHERE due_on <= DATE('now') OR closed_on IS NOT NULL;

INSERT OR IGNORE INTO roles VALUES
    ('engineer', 'Инженер ИБ'), ('master', 'Мастер участка'),
    ('head', 'Руководитель производства'), ('customer', 'Внешний заказчик');
