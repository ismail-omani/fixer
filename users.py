import json
import os

import db

BASE = os.path.dirname(os.path.abspath(__file__))
U_DIR = os.path.join(BASE, "u")

CONTACTS_FILE = "contacts.json"
AVATAR_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
AVATAR_MAX = 2 * 1024 * 1024

AVATAR_COLORS = [
    "#e57373", "#64b5f6", "#81c784", "#ffb74d", "#ba68c8",
    "#4db6ac", "#f06292", "#a1887f", "#90a4ae", "#ff8a65",
]


def user_folder(username):
    return os.path.join(U_DIR, username)


def ensure_folder(username):
    os.makedirs(user_folder(username), exist_ok=True)


# ---------- contacts ----------

def read_contacts(username):
    path = os.path.join(user_folder(username), CONTACTS_FILE)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        result = []
        for item in data:
            if isinstance(item, dict) and "service" in item and "contact" in item:
                result.append({"service": str(item["service"]), "contact": str(item["contact"])})
            elif isinstance(item, str):
                parts = item.split(":", 1)
                if len(parts) == 2:
                    result.append({"contact": parts[0], "service": parts[1]})
        return result
    except (OSError, ValueError):
        return []


def write_contacts(username, contacts):
    ensure_folder(username)
    path = os.path.join(user_folder(username), CONTACTS_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)


def contacts_equal(c1, c2):
    return c1["service"].lower() == c2["service"].lower() and c1["contact"].lower() == c2["contact"].lower()


# ---------- avatar ----------

def avatar_path(username):
    folder = user_folder(username)
    for ext in AVATAR_EXTS:
        path = os.path.join(folder, f"avatar.{ext}")
        if os.path.isfile(path):
            return path
    return None


def save_avatar(username, file_storage):
    if not file_storage or not file_storage.filename:
        return "errors.invalid_input"
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in AVATAR_EXTS:
        return "errors.avatar_type"
    data = file_storage.read()
    if len(data) > AVATAR_MAX:
        return "errors.avatar_size"
    ensure_folder(username)
    for old in AVATAR_EXTS:
        path = os.path.join(user_folder(username), f"avatar.{old}")
        if os.path.isfile(path):
            os.remove(path)
    with open(os.path.join(user_folder(username), f"avatar.{ext}"), "wb") as f:
        f.write(data)
    return None


def delete_avatar(username):
    path = avatar_path(username)
    if path:
        os.remove(path)


def default_avatar_svg(username):
    letter = username[0].upper() if username else "?"
    h = sum(ord(c) for c in username)
    color = AVATAR_COLORS[h % len(AVATAR_COLORS)]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
        f'<rect width="128" height="128" fill="{color}"/>'
        f'<text x="64" y="64" font-size="64" text-anchor="middle" '
        f'dominant-baseline="central" fill="#fff" font-family="sans-serif">{letter}</text>'
        f"</svg>"
    )


# ---------- notifications ----------

def add_notification(user_id, key, **params):
    conn = db.get_db()
    conn.execute(
        "INSERT INTO notifications (user_id, type, payload, created_at) VALUES (?, ?, ?, ?)",
        (user_id, key, json.dumps(params, ensure_ascii=False), db.now_iso()),
    )
    conn.commit()
    conn.close()


def notifications_for(user_id):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        try:
            params = json.loads(row["payload"])
        except ValueError:
            params = {}
        out.append({
            "id": row["id"],
            "key": row["type"],
            "params": params,
            "is_read": bool(row["is_read"]),
            "created_at": row["created_at"].replace("T", " ")[:16],
        })
    return out


def unread_count(user_id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["c"]


def mark_read(notif_id, user_id):
    conn = db.get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notif_id, user_id),
    )
    conn.commit()
    conn.close()


def mark_all_read(user_id):
    conn = db.get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()


def delete_notification(notif_id, user_id):
    conn = db.get_db()
    conn.execute(
        "DELETE FROM notifications WHERE id = ? AND user_id = ?",
        (notif_id, user_id),
    )
    conn.commit()
    conn.close()


def mark_message_notifications_read(user_id, sender_username):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT id, payload FROM notifications WHERE user_id = ? AND type = ? AND is_read = 0",
        (user_id, "notify.message"),
    ).fetchall()
    conn.close()
    ids = []
    for row in rows:
        try:
            params = json.loads(row["payload"])
        except ValueError:
            continue
        if params.get("user") == sender_username:
            ids.append(row["id"])
    if not ids:
        return
    q = ",".join("?" * len(ids))
    conn = db.get_db()
    conn.execute(
        f"UPDATE notifications SET is_read = 1 WHERE id IN ({q}) AND user_id = ?",
        (*ids, user_id),
    )
    conn.commit()
    conn.close()