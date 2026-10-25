"""Persistent memory of the user's category corrections (SQLite).

"Starbucks is Work Meals" is saved once and applied on every later run,
including after a restart.
"""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("data/memory.db")


def merchant_key(description: str) -> str:
    """Stable key for a merchant across months and store numbers.

    "STARBUCKS #1234 AUSTIN TX" -> "STARBUCKS"
    "AMZN MKTP US*2K4LQ8"       -> "AMZN MKTP US"
    "DOORDASH*TACO DELI"        -> "DOORDASH TACO DELI"
    """
    d = description.upper()
    if d.startswith(("DOORDASH*", "SQ *", "TST*")):
        d = d.replace("*", " ", 1)
    d = re.split(r"[*#]", d)[0]
    words = [w for w in d.split() if not any(c.isdigit() for c in w)]
    return " ".join(words[:3]) or description.upper().strip()


class Memory:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS corrections ("
                " merchant TEXT PRIMARY KEY, category TEXT NOT NULL,"
                " example TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def correct(self, description: str, category: str) -> str:
        key = merchant_key(description)
        with self._db() as db:
            db.execute(
                "INSERT INTO corrections VALUES (?, ?, ?, ?) ON CONFLICT(merchant) DO UPDATE"
                " SET category = excluded.category, example = excluded.example, updated_at = excluded.updated_at",
                (key, category, description, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
        return key

    def lookup(self, description: str) -> str | None:
        with self._db() as db:
            row = db.execute(
                "SELECT category FROM corrections WHERE merchant = ?", (merchant_key(description),)
            ).fetchone()
        return row[0] if row else None

    def forget(self, description: str) -> bool:
        with self._db() as db:
            return db.execute(
                "DELETE FROM corrections WHERE merchant = ?", (merchant_key(description),)
            ).rowcount > 0

    def all(self) -> list[tuple[str, str, str, str]]:
        with self._db() as db:
            return db.execute(
                "SELECT merchant, category, example, updated_at FROM corrections ORDER BY merchant"
            ).fetchall()
