"""Хранилище: sqlite. Пользователи, лимиты примерок, заявки, настройки."""
from __future__ import annotations

import contextlib
import os
import sqlite3
from datetime import datetime

import config

_conn: sqlite3.Connection | None = None


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


@contextlib.contextmanager
def db():
    c = _c()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def init_db():
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY, name TEXT, username TEXT,
                is_admin INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS mockups(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id TEXT,
                day TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS leads(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, phone TEXT,
                product_id TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS renders(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id TEXT,
                file_id TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
                product_id TEXT, day TEXT, created_at TEXT
            );
            """
        )
        for uid in config.ADMIN_IDS:
            c.execute("INSERT INTO users(user_id, is_admin) VALUES(?,1) "
                      "ON CONFLICT(user_id) DO UPDATE SET is_admin=1", (uid,))


def get_meta(key, default=None):
    with db() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_meta(key, value):
    with db() as c:
        c.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))


def upsert_user(user_id, name, username):
    with db() as c:
        c.execute("INSERT INTO users(user_id,name,username) VALUES(?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username",
                  (user_id, name, username))


def any_admin_exists() -> bool:
    if config.ADMIN_IDS:
        return True
    with db() as c:
        return c.execute("SELECT 1 FROM users WHERE is_admin=1 LIMIT 1").fetchone() is not None


def make_admin(user_id):
    with db() as c:
        c.execute("INSERT INTO users(user_id,is_admin) VALUES(?,1) "
                  "ON CONFLICT(user_id) DO UPDATE SET is_admin=1", (user_id,))


def is_admin(user_id) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    with db() as c:
        r = c.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,)).fetchone()
    return bool(r and r["is_admin"])


def mockups_today(user_id) -> int:
    day = datetime.now(config.TZ).date().isoformat()
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM mockups WHERE user_id=? AND day=?", (user_id, day)).fetchone()[0]


def log_mockup(user_id, product_id):
    now = datetime.now(config.TZ)
    with db() as c:
        c.execute("INSERT INTO mockups(user_id,product_id,day,created_at) VALUES(?,?,?,?)",
                  (user_id, product_id, now.date().isoformat(), now.isoformat()))


def add_lead(user_id, name, phone, product_id) -> int:
    with db() as c:
        cur = c.execute("INSERT INTO leads(user_id,name,phone,product_id,created_at) VALUES(?,?,?,?,?)",
                        (user_id, name, phone, product_id, datetime.now(config.TZ).isoformat()))
        return cur.lastrowid


def recent_leads(limit=20):
    with db() as c:
        return c.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


# ── примерки пользователя (галерея «Мои примерки») ────────────────────────────
def log_render(user_id, product_id, file_id):
    with db() as c:
        c.execute("INSERT INTO renders(user_id,product_id,file_id,created_at) VALUES(?,?,?,?)",
                  (user_id, product_id, file_id, datetime.now(config.TZ).isoformat()))


def recent_renders(user_id, limit=5):
    with db() as c:
        return c.execute("SELECT * FROM renders WHERE user_id=? ORDER BY id DESC LIMIT ?",
                         (user_id, limit)).fetchall()


# ── события воронки (аналитика) ───────────────────────────────────────────────
def log_event(user_id, name, product_id=None):
    now = datetime.now(config.TZ)
    with db() as c:
        c.execute("INSERT INTO events(user_id,name,product_id,day,created_at) VALUES(?,?,?,?,?)",
                  (user_id, name, product_id, now.date().isoformat(), now.isoformat()))


def event_counts(days=7):
    """Возвращает {event_name: кол-во} за последние N дней и число уникальных юзеров."""
    with db() as c:
        rows = c.execute(
            "SELECT name, COUNT(*) n, COUNT(DISTINCT user_id) u FROM events "
            "WHERE created_at >= datetime('now', ?) GROUP BY name",
            (f"-{int(days)} days",)).fetchall()
    return {r["name"]: {"n": r["n"], "u": r["u"]} for r in rows}
