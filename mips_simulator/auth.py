"""
Authentication module for PyMIPS32 Studio.
Uses Oracle Database when ORACLE_DSN is set; otherwise SQLite (local fallback).
"""

import hashlib
import os
import sqlite3
from pathlib import Path

from exceptions import AuthException

# Optional Oracle driver
try:
    import oracledb
    _ORACLE_AVAILABLE = True
except ImportError:
    _ORACLE_AVAILABLE = False


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class AuthManager:
    """
    Authenticate users against Oracle or a local SQLite database.
    Configure Oracle via environment variables:
      ORACLE_DSN      — e.g. localhost:1521/XEPDB1
      ORACLE_USER     — schema user
      ORACLE_PASSWORD — schema password
    """

    DEFAULT_USERS = {
        "admin": "admin123",
        "student": "mips2024",
    }

    def __init__(self):
        self._use_oracle = bool(os.environ.get("ORACLE_DSN")) and _ORACLE_AVAILABLE
        self._db_path = Path(__file__).parent / "users.db"
        if not self._use_oracle:
            self._init_sqlite()

    @property
    def backend_name(self) -> str:
        return "Oracle Database" if self._use_oracle else "SQLite (local)"

    def _init_sqlite(self):
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    active INTEGER DEFAULT 1
                )
            """)
            for user, pwd in self.DEFAULT_USERS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
                    (user, _hash_password(pwd)),
                )
            conn.commit()
        finally:
            conn.close()

    def _init_oracle(self, conn):
        cur = conn.cursor()
        try:
            cur.execute("""
                BEGIN
                    EXECUTE IMMEDIATE '
                        CREATE TABLE users (
                            username VARCHAR2(64) PRIMARY KEY,
                            password_hash VARCHAR2(128) NOT NULL,
                            active NUMBER(1) DEFAULT 1
                        )';
                EXCEPTION
                    WHEN OTHERS THEN
                        IF SQLCODE != -955 THEN RAISE; END IF;
                END;
            """)
            for user, pwd in self.DEFAULT_USERS.items():
                cur.execute(
                    "MERGE INTO users u USING (SELECT :1 AS u, :2 AS p FROM dual) s "
                    "ON (u.username = s.u) "
                    "WHEN NOT MATCHED THEN INSERT (username, password_hash) VALUES (s.u, s.p)",
                    [user, _hash_password(pwd)],
                )
            conn.commit()
        finally:
            cur.close()

    def _oracle_connect(self):
        if not _ORACLE_AVAILABLE:
            raise AuthException(
                "Oracle DSN configured but oracledb is not installed.",
                context="pip install oracledb",
            )
        dsn = os.environ["ORACLE_DSN"]
        user = os.environ.get("ORACLE_USER", "system")
        password = os.environ.get("ORACLE_PASSWORD", "")
        return oracledb.connect(user=user, password=password, dsn=dsn)

    def authenticate(self, username: str, password: str) -> bool:
        username = (username or "").strip()
        password = password or ""
        if not username or not password:
            raise AuthException("Username and password are required.")

        pwd_hash = _hash_password(password)

        if self._use_oracle:
            return self._auth_oracle(username, pwd_hash)
        return self._auth_sqlite(username, pwd_hash)

    def _auth_sqlite(self, username: str, pwd_hash: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT password_hash, active FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if not row:
                raise AuthException("Invalid username or password.", context=username)
            stored, active = row
            if not active:
                raise AuthException("Account is disabled.", context=username)
            if stored != pwd_hash:
                raise AuthException("Invalid username or password.", context=username)
            return True
        finally:
            conn.close()

    def _auth_oracle(self, username: str, pwd_hash: str) -> bool:
        conn = self._oracle_connect()
        try:
            self._init_oracle(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT password_hash, active FROM users WHERE username = :u",
                {"u": username},
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                raise AuthException("Invalid username or password.", context=username)
            stored, active = row
            if not active:
                raise AuthException("Account is disabled.", context=username)
            if stored != pwd_hash:
                raise AuthException("Invalid username or password.", context=username)
            return True
        except AuthException:
            raise
        except Exception as ex:
            raise AuthException(f"Oracle connection failed: {ex}") from ex
        finally:
            conn.close()
