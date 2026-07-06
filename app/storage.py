import os
import sqlite3
from contextlib import closing


class StateStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS status (
                    sheet TEXT NOT NULL,
                    row INTEGER NOT NULL,
                    phone_status TEXT,
                    attendance_status TEXT,
                    PRIMARY KEY (sheet, row)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    selected_operator TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    def load_all(self):
        with closing(sqlite3.connect(self.path)) as conn:
            rows = conn.execute(
                "SELECT sheet, row, phone_status, attendance_status FROM status"
            ).fetchall()
        return {(sheet, row): (phone_status, attendance_status) for sheet, row, phone_status, attendance_status in rows}

    def set_status(self, sheet, row, phone_status=None, attendance_status=None):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                """
                INSERT INTO status (sheet, row, phone_status, attendance_status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sheet, row) DO UPDATE SET
                    phone_status = COALESCE(excluded.phone_status, status.phone_status),
                    attendance_status = COALESCE(excluded.attendance_status, status.attendance_status)
                """,
                (sheet, row, phone_status, attendance_status),
            )
            conn.commit()

    def clear(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DELETE FROM status")
            conn.commit()

    def get_selected_operator(self, user_id):
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute(
                "SELECT selected_operator FROM user_prefs WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row[0] if row else None

    def set_selected_operator(self, user_id, operator):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                """
                INSERT INTO user_prefs (user_id, selected_operator) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET selected_operator = excluded.selected_operator
                """,
                (user_id, operator),
            )
            conn.commit()

    def get_config(self, key, default=None):
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute("SELECT value FROM bot_config WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_config(self, key, value):
        with closing(sqlite3.connect(self.path)) as conn:
            if value is None:
                conn.execute("DELETE FROM bot_config WHERE key = ?", (key,))
            else:
                conn.execute(
                    """
                    INSERT INTO bot_config (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
            conn.commit()
