import json
import os
import re
import secrets
import shutil
import string

import db
import users

BASE = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(BASE, "tasks")

ID_ALPHABET = string.digits + string.ascii_letters
ID_LENGTH = 16

MAX_FILE_SIZE = 25 * 1024 * 1024


def task_dir(task_id):
    return os.path.join(TASKS_DIR, task_id)


def gen_id(length=ID_LENGTH):
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(length))


def _safe_filename(name):
    name = os.path.basename(name or "")
    name = re.sub(r"[\x00-\x1f]", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    name = name.strip(". ")
    return name[:150] or "file"


def _sanitize_title(title):
    name = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", title).strip().strip(".")
    return name[:120] or "task"


def _write_meta(meta):
    path = os.path.join(task_dir(meta["id"]), "meta.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_task(task_id):
    d = task_dir(task_id)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    meta["id"] = task_id
    md_files = sorted(x for x in os.listdir(d) if x.endswith(".md"))
    meta["body_file"] = md_files[0] if md_files else None
    meta["body"] = ""
    if meta["body_file"]:
        try:
            with open(os.path.join(d, meta["body_file"]), encoding="utf-8") as f:
                meta["body"] = f.read()
        except OSError:
            meta["body"] = ""
    files_dir = os.path.join(d, "files")
    meta["files"] = sorted(os.listdir(files_dir)) if os.path.isdir(files_dir) else []
    return meta


def _write_body(meta, title, text):
    d = task_dir(meta["id"])
    if meta.get("body_file") and os.path.isfile(os.path.join(d, meta["body_file"])):
        os.remove(os.path.join(d, meta["body_file"]))
    fname = _sanitize_title(title) + ".md"
    with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
        f.write(text or "")
    meta["body_file"] = fname


def _save_uploads(meta, uploads):
    if not uploads:
        return
    d = task_dir(meta["id"])
    files_dir = os.path.join(d, "files")
    os.makedirs(files_dir, exist_ok=True)
    for up in uploads:
        if not up or not up.filename:
            continue
        data = up.read()
        if len(data) > MAX_FILE_SIZE:
            continue
        name = _safe_filename(up.filename)
        base, ext = os.path.splitext(name)
        path = os.path.join(files_dir, name)
        n = 1
        while os.path.exists(path):
            path = os.path.join(files_dir, f"{base}_{n}{ext}")
            n += 1
        with open(path, "wb") as f:
            f.write(data)


def create_task(author, title, text, uploads):
    title = (title or "").strip()
    if not title:
        return None, "errors.title_required"
    os.makedirs(TASKS_DIR, exist_ok=True)
    task_id = gen_id()
    while os.path.exists(task_dir(task_id)):
        task_id = gen_id()
    os.makedirs(task_dir(task_id))
    os.makedirs(os.path.join(task_dir(task_id), "files"), exist_ok=True)
    meta = {
        "id": task_id,
        "author": author,
        "title": title,
        "created_at": db.now_iso(),
        "status": "active",
        "booked_by": None,
        "refusals": [],
        "completion": {"requested_by": None},
    }
    _write_body(meta, title, text)
    _write_meta(meta)
    _save_uploads(meta, uploads)
    return task_id, None


def update_task(task_id, author, title, text, uploads, delete_files):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["author"] != author:
        return "errors.not_author"
    if meta["status"] != "active":
        return "errors.not_allowed"
    title = (title or "").strip()
    if not title:
        return "errors.title_required"
    meta["title"] = title
    _write_body(meta, title, text)
    _write_meta(meta)
    if delete_files:
        d = task_dir(task_id)
        files_dir = os.path.join(d, "files")
        for name in delete_files:
            safe = _safe_filename(name)
            path = os.path.join(files_dir, safe)
            if os.path.isfile(path) and os.path.basename(path) == safe:
                os.remove(path)
    _save_uploads(meta, uploads)
    return None


def delete_task(task_id, author):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["author"] != author:
        return "errors.not_author"
    if meta["status"] != "active":
        return "errors.not_allowed"
    shutil.rmtree(task_dir(task_id), ignore_errors=True)
    return None


# ---------- lifecycle ----------

def is_author(task, username):
    return task["author"] == username


def is_executor(task, username):
    return task["status"] == "booked" and task["booked_by"] == username


def is_refused(task, username):
    return any(r["username"] == username for r in task["refusals"])


def respond(task_id, username):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["status"] != "active":
        return "errors.booked"
    if meta["author"] == username:
        return "errors.not_allowed"
    if is_refused(meta, username):
        return "errors.refused"
    meta["status"] = "booked"
    meta["booked_by"] = username
    meta["completion"] = {"requested_by": None}
    _write_meta(meta)
    author_id = db.get_user_id(meta["author"])
    if author_id:
        users.add_notification(author_id, "notify.respond", user=username, title=meta["title"])
    return None


def refuse_executor(task_id, author, username, reason):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["author"] != author:
        return "errors.not_author"
    if meta["status"] != "booked" or meta["booked_by"] != username:
        return "errors.not_allowed"
    _unbook(meta, username, reason)
    refused_id = db.get_user_id(username)
    if refused_id:
        users.add_notification(refused_id, "notify.refuse_author", title=meta["title"])
    return None


def refuse_self(task_id, executor, reason):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if not is_executor(meta, executor):
        return "errors.not_allowed"
    _unbook(meta, executor, reason)
    author_id = db.get_user_id(meta["author"])
    if author_id:
        users.add_notification(author_id, "notify.refuse_executor", user=executor, title=meta["title"])
    return None


def _unbook(meta, username, reason):
    meta["status"] = "active"
    meta["booked_by"] = None
    meta["completion"] = {"requested_by": None}
    meta["refusals"].append({"username": username, "reason": (reason or "").strip()})
    _write_meta(meta)


def request_completion(task_id, username):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["status"] != "booked":
        return "errors.not_allowed"
    if username not in (meta["author"], meta["booked_by"]):
        return "errors.not_allowed"
    if meta["completion"].get("requested_by"):
        return "errors.not_allowed"
    meta["completion"]["requested_by"] = username
    _write_meta(meta)
    other = meta["booked_by"] if username == meta["author"] else meta["author"]
    other_id = db.get_user_id(other)
    if other_id:
        users.add_notification(other_id, "notify.complete_request", user=username, title=meta["title"])
    return None


def respond_completion(task_id, username, action):
    meta = load_task(task_id)
    if not meta:
        return "errors.task_not_found"
    if meta["status"] != "booked":
        return "errors.not_allowed"
    if username not in (meta["author"], meta["booked_by"]):
        return "errors.not_allowed"
    requester = meta["completion"].get("requested_by")
    if not requester or requester == username:
        return "errors.not_allowed"
    if action == "accept":
        meta["status"] = "completed"
        meta["completion"]["requested_by"] = None
        meta["completion"]["accepted_by"] = username
        meta["completed_at"] = db.now_iso()
        _write_meta(meta)
        requester_id = db.get_user_id(requester)
        if requester_id:
            users.add_notification(requester_id, "notify.complete_accepted", title=meta["title"])
    elif action == "reject":
        meta["completion"]["requested_by"] = None
        _write_meta(meta)
        requester_id = db.get_user_id(requester)
        if requester_id:
            users.add_notification(requester_id, "notify.complete_rejected", title=meta["title"])
    else:
        return "errors.invalid_input"
    return None


# ---------- listing & search ----------

def list_tasks(statuses, q=""):
    os.makedirs(TASKS_DIR, exist_ok=True)
    q = (q or "").strip().lower()
    results = []
    for name in os.listdir(TASKS_DIR):
        meta = load_task(name)
        if not meta:
            continue
        if meta["status"] not in statuses:
            continue
        if q:
            hay = " ".join([meta["id"], meta["title"], meta["body"], " ".join(meta["files"])]).lower()
            if q not in hay:
                continue
        results.append(meta)
    results.sort(key=lambda t: t["created_at"], reverse=True)
    return results


def user_tasks(username, role, statuses):
    """role: 'executor' (booked_by == username) or 'author' (author == username)."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    out = []
    for name in os.listdir(TASKS_DIR):
        meta = load_task(name)
        if not meta:
            continue
        if meta["status"] not in statuses:
            continue
        if role == "executor" and meta["booked_by"] == username:
            out.append(meta)
        elif role == "author" and meta["author"] == username:
            out.append(meta)
    out.sort(key=lambda t: t["created_at"], reverse=True)
    return out