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
