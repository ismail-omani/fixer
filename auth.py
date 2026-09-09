import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
SESSION_TTL_DAYS = 30
MAX_PASSWORD_LEN = 128


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def validate_username(username):
    if not USERNAME_RE.match(username):
        return "errors.username_invalid"
    if "admin" in username.lower():
        return "errors.username_admin"
    return None


def register(username, password):
    username = username.strip()
    err = validate_username(username)
    if err:
        return False, err
    if len(password) < 6 or len(password) > MAX_PASSWORD_LEN:
        return False, "errors.password_short"
    conn = db.get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if existing:
        conn.close()
        return False, "errors.username_taken"
    phash = generate_password_hash(password)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, phash, db.now_iso()),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return True, uid


def authenticate(username, password):
    row = db.get_user(username)
    if not row or not check_password_hash(row["password_hash"], password):
        return None
    return row


def create_session(user_id):
    sid = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    conn = db.get_db()
    conn.execute(
        "INSERT INTO sessions (token, csrf, user_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (sid, csrf, user_id, _iso(_now()), _iso(_now() + timedelta(days=SESSION_TTL_DAYS))),
    )
    conn.commit()
    conn.close()
    return sid, csrf


def load_session(sid):
    if not sid:
        return None
    conn = db.get_db()
    row = conn.execute(
        "SELECT s.csrf AS csrf, s.expires_at AS expires_at, u.id AS uid, u.username AS username "
        "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (sid,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    if row["expires_at"] < _iso(_now()):
        return None
    return {"id": row["uid"], "username": row["username"], "csrf": row["csrf"]}


def delete_session(sid):
    if not sid:
        return
    conn = db.get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (sid,))
    conn.commit()
    conn.close()


def purge_expired_sessions():
    conn = db.get_db()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(_now()),))
    conn.commit()
    conn.close()


def set_cookie(resp, sid):
    resp.set_cookie(
        "sid",
        sid,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        samesite="Lax",
    )
    return resp


def clear_cookie(resp):
    resp.delete_cookie("sid")
    return resp