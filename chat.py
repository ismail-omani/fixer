import os
import re

import db
import users

BASE = os.path.dirname(os.path.abspath(__file__))
CHAT_FILES_DIR = os.path.join(BASE, "chat_files")

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_BODY_LEN = 4000


# ---------- helpers ----------

def _safe_filename(name):
    name = os.path.basename(name or "")
    name = re.sub(r"[\x00-\x1f]", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    name = name.strip(". ")
    return name[:150] or "file"


def conv_files_dir(conv_id):
    return os.path.join(CHAT_FILES_DIR, str(conv_id))


# ---------- conversations ----------

def get_or_create(user1_id, user2_id):
    user_a, user_b = sorted((user1_id, user2_id))
    conn = db.get_db()
    row = conn.execute(
        "SELECT id FROM conversations WHERE user_a = ? AND user_b = ?",
        (user_a, user_b),
    ).fetchone()
    if row:
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO conversations (user_a, user_b, created_at) VALUES (?, ?, ?)",
        (user_a, user_b, db.now_iso()),
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def has_conversation(user1_id, user2_id):
    user_a, user_b = sorted((user1_id, user2_id))
    conn = db.get_db()
    row = conn.execute(
        "SELECT id FROM conversations WHERE user_a = ? AND user_b = ?", (user_a, user_b)
    ).fetchone()
    conn.close()
    return bool(row)


def conversation(conv_id):
    conn = db.get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def is_participant(conv, user_id):
    return conv and user_id in (conv["user_a"], conv["user_b"])


def other_user(conv, user_id):
    return conv["user_b"] if conv["user_a"] == user_id else conv["user_a"]


# ---------- messages ----------

def messages(conv_id):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT m.*, u.username AS sender_name FROM messages m "
        "JOIN users u ON u.id = m.sender_id "
        "WHERE m.conversation_id = ? ORDER BY m.id ASC",
        (conv_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def last_message_id(conv_id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT MAX(id) AS mid FROM messages WHERE conversation_id = ?", (conv_id,)
    ).fetchone()
    conn.close()
    return row["mid"] or 0


def send(conv_id, sender_id, body, file_storage=None):
    body = (body or "").strip()
    attachment = None
    if file_storage and file_storage.filename:
        data = file_storage.read()
        if len(data) > MAX_FILE_SIZE:
            return None, "errors.file_too_big"
        if not body:
            body = ""
        attachment = _save_attachment(conv_id, file_storage.filename, data)
    if not body and not attachment:
        return None, "errors.invalid_input"
    body = body[:MAX_BODY_LEN]
    conn = db.get_db()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, sender_id, body, attachment, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (conv_id, sender_id, body, attachment, db.now_iso()),
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return msg_id, None


def new_messages(conv_id, after_id):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT m.*, u.username AS sender_name FROM messages m "
        "JOIN users u ON u.id = m.sender_id "
        "WHERE m.conversation_id = ? AND m.id > ? ORDER BY m.id ASC",
        (conv_id, after_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _save_attachment(conv_id, filename, data):
    d = conv_files_dir(conv_id)
    os.makedirs(d, exist_ok=True)
    name = _safe_filename(filename)
    base, ext = os.path.splitext(name)
    path = os.path.join(d, name)
    n = 1
    while os.path.exists(path):
        path = os.path.join(d, f"{base}_{n}{ext}")
        n += 1
    with open(path, "wb") as f:
        f.write(data)
    return os.path.basename(path)


def attachment_path(conv_id, name):
    d = conv_files_dir(conv_id)
    safe = _safe_filename(name)
    path = os.path.join(d, safe)
    if os.path.isfile(path) and os.path.basename(path) == safe:
        return path
    return None


# ---------- read state ----------

def unread_count(conv_id, user_id):
    conv = conversation(conv_id)
    if not conv:
        return 0
    read_col = "user_a_read_id" if conv["user_a"] == user_id else "user_b_read_id"
    conn = db.get_db()
    row = conn.execute(
        f"SELECT COUNT(*) AS c FROM messages WHERE conversation_id = ? "
        f"AND sender_id != ? AND id > ?",
        (conv_id, user_id, conv[read_col]),
    ).fetchone()
    conn.close()
    return row["c"]


def mark_read(conv_id, user_id):
    conv = conversation(conv_id)
    if not conv or not is_participant(conv, user_id):
        return
    read_col = "user_a_read_id" if conv["user_a"] == user_id else "user_b_read_id"
    mid = last_message_id(conv_id)
    conn = db.get_db()
    conn.execute(f"UPDATE conversations SET {read_col} = ? WHERE id = ?", (mid, conv_id))
    conn.commit()
    conn.close()


def total_unread(user_id):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM conversations WHERE user_a = ? OR user_b = ?", (user_id, user_id)
    ).fetchall()
    conn.close()
    total = 0
    for row in rows:
        conv = dict(row)
        total += unread_count(conv["id"], user_id)
    return total


# ---------- listing ----------

def conversations_for(user_id):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM conversations WHERE user_a = ? OR user_b = ?", (user_id, user_id)
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        conv = dict(row)
        other_id = other_user(conv, user_id)
        other = conn_row_user(other_id)
        if not other:
            continue
        msgs = messages(conv["id"])
        last = msgs[-1] if msgs else None
        if last:
            last["mine"] = last["sender_id"] == user_id
        out.append({
            "id": conv["id"],
            "other_id": other_id,
            "other_name": other,
            "last": last,
            "unread": unread_count(conv["id"], user_id),
        })
    out.sort(key=lambda c: c["last"]["id"] if c["last"] else 0, reverse=True)
    return out


def conn_row_user(user_id):
    conn = db.get_db()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["username"] if row else None