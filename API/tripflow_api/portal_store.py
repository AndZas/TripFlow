import hashlib
import secrets
import time
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .database import Database


SESSION_SECONDS = 12 * 60 * 60
password_hasher = PasswordHasher()


class RegistrationError(Exception):
    pass


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def valid_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


class PortalStore:
    def __init__(self, database: Database):
        self.db = database
        self.dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))
        with database.transaction():
            database.execute("""
                CREATE TABLE IF NOT EXISTS portal_accounts (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
                    api_hash TEXT UNIQUE, api_hint TEXT, api_issued INTEGER,
                    access_status TEXT NOT NULL,
                    owner_review INTEGER NOT NULL DEFAULT 0
                )
            """)
            if "access_status" not in database.columns("portal_accounts"):
                database.execute("ALTER TABLE portal_accounts ADD COLUMN access_status TEXT")
                database.execute("UPDATE portal_accounts SET access_status = CASE WHEN active = 1 THEN 'approved' ELSE 'disabled' END")
            if "owner_review" not in database.columns("portal_accounts"):
                database.execute("ALTER TABLE portal_accounts ADD COLUMN owner_review INTEGER NOT NULL DEFAULT 0")
                database.execute("UPDATE portal_accounts SET owner_review = 1 WHERE access_status = 'disabled'")
            database.execute("CREATE UNIQUE INDEX IF NOT EXISTS portal_one_owner ON portal_accounts(role) WHERE role = 'owner'")
            database.execute("""
                CREATE TABLE IF NOT EXISTS portal_sessions (
                    token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires_at INTEGER NOT NULL
                )
            """)
            database.execute("CREATE INDEX IF NOT EXISTS portal_sessions_account ON portal_sessions(account_id)")

    def bootstrap_owner(self, email: str, password: str) -> bool:
        with self.db.transaction():
            if self.one("SELECT id FROM portal_accounts WHERE role = 'owner'", ()):
                return True
            legacy_admins = self.db.records("SELECT id, email FROM portal_accounts WHERE role = 'admin'")
            if legacy_admins:
                candidates = [admin for admin in legacy_admins if admin["email"] == email] if email else legacy_admins
                if len(candidates) != 1:
                    raise ValueError("Set TRIPFLOW_PORTAL_ADMIN_EMAIL to the existing owner email for migration")
                self.db.execute(
                    "UPDATE portal_accounts SET role = 'owner' WHERE id = ?", (candidates[0]["id"],)
                )
                return True
            if not email and not password:
                return False
            if not email or not 1 <= len(password) <= 128:
                raise ValueError("Set both TRIPFLOW_PORTAL_ADMIN_EMAIL and TRIPFLOW_PORTAL_ADMIN_PASSWORD for the first startup")
            if self.find_email(email):
                raise ValueError("The bootstrap email already belongs to a portal account")
            self.db.execute(
                "INSERT INTO portal_accounts (id, email, password_hash, role, active, created_at, access_status) "
                "VALUES (?, ?, ?, 'owner', 1, ?, 'approved')",
                (uuid4().hex, email, password_hasher.hash(password), int(time.time())),
            )
            return True

    def one(self, query: str, args: tuple):
        rows = self.db.records(query, args)
        return rows[0] if rows else None

    def find_email(self, email: str) -> dict | None:
        return self.one("SELECT * FROM portal_accounts WHERE email = ?", (email,))

    def register(self, email: str, password_hash: str) -> None:
        inserted = self.db.execute(
            "INSERT INTO portal_accounts (id,email,password_hash,role,active,created_at,access_status) "
            "VALUES (?,?,?,'developer',0,?,'pending') ON CONFLICT(email) DO NOTHING",
            (uuid4().hex, email, password_hash, int(time.time())),
        )
        if not inserted.rowcount:
            raise RegistrationError("Для этого email уже есть аккаунт. Войдите, чтобы проверить статус.")

    def reapply(self, account_id: str, password_hash: str) -> bool:
        changed = self.db.execute(
            "UPDATE portal_accounts SET access_status = 'pending' "
            "WHERE id = ? AND role = 'developer' AND password_hash = ? AND access_status IN ('disabled', 'rejected')",
            (account_id, password_hash),
        )
        return bool(changed.rowcount)

    def start_session(self, account_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.db.transaction():
            self.db.execute("DELETE FROM portal_sessions WHERE expires_at <= ?", (now,))
            self.db.execute(
                "INSERT INTO portal_sessions VALUES (?, ?, ?)", (digest(token), account_id, now + SESSION_SECONDS)
            )
        return token

    def find_session(self, token: str) -> dict | None:
        return self.one(
            "SELECT a.* FROM portal_sessions s JOIN portal_accounts a ON a.id = s.account_id "
            "WHERE s.token_hash = ? AND s.expires_at > ? AND a.active = 1",
            (digest(token), int(time.time())),
        )

    def end_session(self, token: str) -> None:
        with self.db.transaction():
            self.db.execute("DELETE FROM portal_sessions WHERE token_hash = ?", (digest(token),))

    def client_by_key(self, key: str) -> str | None:
        row = self.db.execute(
            "SELECT id FROM portal_accounts WHERE active = 1 AND api_hash = ?", (digest(key),)
        ).fetchone()
        return row[0] if row else None

    def issue_key(self, account_id: str) -> str:
        key = "tf_api_" + secrets.token_urlsafe(32)
        self.db.execute("UPDATE portal_accounts SET api_hash = ?, api_hint = ?, api_issued = ? WHERE id = ?",
                        (digest(key), key[-6:], int(time.time()), account_id))
        return key

    def revoke_key(self, account_id: str) -> None:
        self.db.execute("UPDATE portal_accounts SET api_hash = NULL, api_hint = NULL, api_issued = NULL WHERE id = ?", (account_id,))

    def accounts(self, actor_role: str):
        if actor_role == "owner":
            return self.db.records("SELECT * FROM portal_accounts ORDER BY created_at DESC, email")
        return self.db.records("SELECT * FROM portal_accounts WHERE role = 'developer' ORDER BY created_at DESC, email")

    def find_account(self, account_id: str):
        return self.one("SELECT * FROM portal_accounts WHERE id = ?", (account_id,))

    def change_role(self, account_id: str, action: str) -> bool:
        previous, role = ("developer", "admin") if action == "promote" else ("admin", "developer")
        changed = self.db.execute(
            "UPDATE portal_accounts SET role = ? WHERE id = ? AND role = ? AND access_status = 'approved'",
            (role, account_id, previous),
        )
        return bool(changed.rowcount)

    def disable(self, account_id: str) -> bool:
        with self.db.transaction():
            changed = self.db.execute(
                "UPDATE portal_accounts SET active = 0, access_status = 'disabled', role = 'developer', "
                "owner_review = 1 "
                "WHERE id = ? AND role IN ('developer', 'admin') AND access_status = 'approved'",
                (account_id,),
            )
            if changed.rowcount:
                self.db.execute("DELETE FROM portal_sessions WHERE account_id = ?", (account_id,))
                self.revoke_key(account_id)
        return bool(changed.rowcount)

    def decide(self, account_id: str, action: str, actor_role: str) -> bool:
        approved = action == "approve"
        changed = self.db.execute(
            "UPDATE portal_accounts SET active = ?, access_status = ?, "
            "owner_review = CASE WHEN ? = 1 THEN 0 ELSE owner_review END "
            "WHERE id = ? AND role = 'developer' AND access_status = 'pending' AND (owner_review = 0 OR ? = 'owner')",
            (int(approved), "approved" if approved else "rejected", int(approved), account_id, actor_role),
        )
        return bool(changed.rowcount)
