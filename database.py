import sqlite3
import json
from typing import Optional, List


class Database:
    def __init__(self, db_path: str = "waveforms.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS waveforms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    wave_type TEXT NOT NULL,
                    sea_type TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    amplitude REAL,
                    frequency REAL,
                    period REAL
                )
            """)
            try:
                conn.execute("ALTER TABLE waveforms ADD COLUMN data TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def save_waveform(
        self,
        wave_type: str,
        sea_type: str,
        channel: str,
        amplitude: Optional[float] = None,
        frequency: Optional[float] = None,
        period: Optional[float] = None,
        data: Optional[List[float]] = None
    ) -> int:
        data_json = json.dumps(data) if data is not None else None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO waveforms 
                (wave_type, sea_type, channel, amplitude, frequency, period, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (wave_type, sea_type, channel, amplitude, frequency, period, data_json))
            conn.commit()
            return cursor.lastrowid

    def get_recent(self, limit: int = 10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM waveforms 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    def get_since_id(self, since_id: int, limit: int = 500):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM waveforms 
                WHERE id > ?
                ORDER BY id DESC 
                LIMIT ?
            """, (since_id, limit))
            return cursor.fetchall()

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM waveforms")
            conn.commit()

    def get_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM waveforms ORDER BY timestamp DESC")
            return cursor.fetchall()