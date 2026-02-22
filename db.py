# bot/db.py
import os, sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_PATH = os.environ.get("DB_PATH", "data/db.sqlite")

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS tasks (
        id           TEXT PRIMARY KEY,
        user_id      INTEGER NOT NULL,
        chat_id      INTEGER NOT NULL,
        text         TEXT    NOT NULL,
        tz           TEXT    NOT NULL,
        kind         TEXT    NOT NULL,   -- 'snooze' | 'daily_at' | 'interval'
        snooze_min   INTEGER,            -- for snooze / post-fire snooze
        daily_hour   INTEGER,
        daily_minute INTEGER,
        interval_h   INTEGER,
        remaining    INTEGER,            -- NULL = infinite
        active       INTEGER NOT NULL DEFAULT 1,
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS schedules (
        task_id      TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
        next_run_utc TEXT NOT NULL,      -- ISO8601 UTC
        claimed_until TEXT
        );

        CREATE INDEX IF NOT EXISTS schedules_due_idx ON schedules(next_run_utc);
        """
    )
    conn.close()

def _iso(dt):  # store naive UTC ISO string
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")

def _parse_iso(s):
    # sqlite stores naive; treat as UTC
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

def create_task_snooze(task_id, user_id, chat_id, text, tz, snooze_min, first_when_aware_utc):
    conn = _connect(); cur = conn.cursor()
    
    cur.execute(
        """INSERT INTO tasks(id,user_id,chat_id,text,tz,kind,snooze_min,active) VALUES(?,?,?,?,?,'snooze',?,1)""", 
            (task_id, user_id, chat_id, text, tz, snooze_min))
    
    cur.execute("""INSERT INTO schedules(task_id,next_run_utc) VALUES(?,?)""", 
            (task_id, _iso(first_when_aware_utc)))
    
    conn.close()

def list_tasks(user_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY created_at", (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def mark_done(user_id, task_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute("UPDATE tasks SET active=0 WHERE id=? AND user_id=?", (task_id, user_id))
    cur.execute("DELETE FROM schedules WHERE task_id=?", (task_id,))
    ok = cur.rowcount > 0
    conn.close()
    return ok

def _next_daily(now_local, hour, minute):
    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate if candidate > now_local else candidate + timedelta(days=1)

def _compute_next_run(task_row, fired_at_utc):
    kind = task_row["kind"]
    if kind == "snooze":
        mins = int(task_row["snooze_min"] or 60)
        return fired_at_utc + timedelta(minutes=mins)
    if kind == "daily_at":
        tz = ZoneInfo(task_row["tz"])
        now_local = fired_at_utc.astimezone(tz)
        nxt_local = _next_daily(now_local, int(task_row["daily_hour"]), int(task_row["daily_minute"]))
        return nxt_local.astimezone(timezone.utc)
    if kind == "interval":
        return fired_at_utc + timedelta(hours=int(task_row["interval_h"]))
    raise ValueError("unknown kind")

async def scheduler_tick(context):
    """Run every 30–60s. Fires due reminders and moves next_run_utc forward."""
    conn = _connect(); cur = conn.cursor()
    now_utc = datetime.now(timezone.utc)

    # single-instance simple due selection
    cur.execute("""
      SELECT t.*, s.next_run_utc
      FROM schedules s JOIN tasks t ON t.id=s.task_id
      WHERE t.active=1 AND s.next_run_utc <= ?
      ORDER BY s.next_run_utc ASC
      LIMIT 50
    """, (_iso(now_utc),))
    due = cur.fetchall()

    for row in due:
        chat_id = row["chat_id"]
        task_id = row["id"]
        text = row["text"]

        # 1) send
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"{text}.\nReply with /done {task_id} to stop")
        except Exception as e:
            # leave next_run_utc as-is; will retry next tick
            continue

        # 2) finite series?
        if row["remaining"] is not None:
            remaining = int(row["remaining"]) - 1
            if remaining <= 0:
                cur.execute("UPDATE tasks SET active=0, remaining=0 WHERE id=?", (task_id,))
                cur.execute("DELETE FROM schedules WHERE task_id=?", (task_id,))
                continue
            cur.execute("UPDATE tasks SET remaining=? WHERE id=?", (remaining, task_id,))

        # 3) compute next run and update
        next_run = _compute_next_run(row, now_utc)
        cur.execute("UPDATE schedules SET next_run_utc=? WHERE task_id=?", (_iso(next_run), task_id))

    conn.close()