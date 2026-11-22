import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg


class Database:
    def __init__(self, sqlite_path: Path):
        url = os.environ.get("DATABASE_URL")
        self.postgres = bool(url)
        if url:
            self.connection = psycopg.connect(url, autocommit=True)
        else:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(sqlite_path, isolation_level=None)

    def execute(self, sql, args=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.connection.execute(sql, args)

    def records(self, sql, args=()):
        cursor = self.execute(sql, args)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def columns(self, table):
        if self.postgres:
            rows = self.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = ?",
                (table,),
            )
            return {row[0] for row in rows}
        return {row[1] for row in self.execute(f"PRAGMA table_info({table})")}

    @contextmanager
    def transaction(self):
        self.execute("BEGIN" if self.postgres else "BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.execute("ROLLBACK")
            raise
        else:
            self.execute("COMMIT")

    def close(self):
        self.connection.close()
