import os
import time
from functools import wraps


def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

import bleach
import markdown as md_lib
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

import auth
import chat
import db
import i18n
import tasks
import users

BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FIXER_HTTPS", "").lower() in ("1", "true", "yes")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ALLOWED_MD_TAGS = [
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "u", "s", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td",
]
ALLOWED_MD_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "pre": ["class"],
}
ALLOWED_MD_PROTOCOLS = ["http", "https", "mailto"]

_login_attempts = {}
LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW = 60


@app.after_request
def add_security_headers(resp):
    resp.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if "Server" in resp.headers:
        del resp.headers["Server"]
    return resp


def render_markdown(text):
    html = md_lib.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])
    return bleach.clean(
        html,
        tags=ALLOWED_MD_TAGS,
        attributes=ALLOWED_MD_ATTRS,
        protocols=ALLOWED_MD_PROTOCOLS,
        strip=True,
    )


def get_lang():
    return i18n.get_lang(request)


@app.before_request
def load_user():
    g.user = None
    g.csrf = None
    sid = request.cookies.get("sid")
    if sid:
        session = auth.load_session(sid)
        if session:
            g.user = {"id": session["id"], "username": session["username"]}
            g.csrf = session["csrf"]


@app.context_processor
def inject_globals():
    unread = 0
    chat_unread = 0
    if g.get("user"):
        unread = users.unread_count(g.user["id"])
        chat_unread = chat.total_unread(g.user["id"])
    lang = get_lang()

    def t(key, **kwargs):
        return i18n.translate(lang, key, **kwargs)

    return {"t": t, "lang": lang, "unread": unread, "chat_unread": chat_unread}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("user"):
            return redirect(url_for("register"))
        return fn(*args, **kwargs)

    return wrapper


def csrf_protect(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get("csrf", "")
            if not g.get("csrf") or token != g.csrf:
                abort(400)
        return fn(*args, **kwargs)

    return wrapper


# ---------- language ----------

@app.route("/set_lang/<lang>")
def set_lang(lang):
    if lang not in i18n.LANGUAGES:
        lang = "ru"
    resp = redirect(request.referrer or url_for("index"))
    resp.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax")
    return resp


# ---------- auth ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and g.get("user"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        ip = request.remote_addr
        now = time.time()
        attempts = _login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < LOGIN_RATE_WINDOW]
        if len(attempts) >= LOGIN_RATE_LIMIT:
            error = "errors.too_many_attempts"
            _login_attempts[ip] = attempts
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            row = auth.authenticate(username, password)
            if not row:
                error = "errors.invalid_credentials"
                attempts.append(now)
                _login_attempts[ip] = attempts
            else:
                _login_attempts.pop(ip, None)
                old_sid = request.cookies.get("sid")
                if old_sid:
                    auth.delete_session(old_sid)
                sid, _csrf = auth.create_session(row["id"])
                resp = auth.set_cookie(redirect(url_for("index")), sid)
                return resp
    return render_template("auth.html", mode="login", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        contacts = []
        services = request.form.getlist("service")
        contact_values = request.form.getlist("contact")
        for svc, val in zip(services, contact_values):
            svc = svc.strip()
            val = val.strip()
            if svc and val:
                contacts.append({"service": svc, "contact": val})
        if not contacts:
            error = "errors.contacts_required"
        elif password != password2:
            error = "errors.password_mismatch"
        else:
            ok, res = auth.register(username, password)
            if not ok:
                error = res
            else:
                users.write_contacts(username, contacts)
                sid, _csrf = auth.create_session(res)
                resp = auth.set_cookie(redirect(url_for("index")), sid)
                return resp
    return render_template("auth.html", mode="register", error=error)


@app.route("/logout", methods=["POST"])
@login_required
@csrf_protect
def logout():
    auth.delete_session(request.cookies.get("sid"))
    resp = auth.clear_cookie(redirect(url_for("register")))
    return resp


# ---------- pages ----------

def _task_list(mode, q):
    statuses = {"active", "booked"} if mode == "active" else {"completed"}
    return tasks.list_tasks(statuses, q)


@app.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    task_list = _task_list("active", q)
    return render_template("index.html", task_list=task_list, q=q, mode="active")


@app.route("/completed")
@login_required
def completed():
    q = request.args.get("q", "").strip()
    task_list = _task_list("completed", q)
    return render_template("index.html", task_list=task_list, q=q, mode="completed")


@app.route("/feed")
@login_required
def feed():
    mode = request.args.get("mode", "active")
    if mode not in ("active", "completed"):
        mode = "active"
    q = request.args.get("q", "").strip()
    task_list = _task_list(mode, q)
    resp = make_response(render_template("_feed.html", task_list=task_list, q=q, mode=mode))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/top")
@login_required
def top():
    return render_template("stats.html", rows=tasks.top_executors(10))


@app.route("/tasks/<task_id>")
@login_required
def task_page(task_id):
    meta = tasks.load_task(task_id)
    if not meta:
        abort(404)
    user = g.user
    ctx = {
        "task": meta,
        "body_html": render_markdown(meta["body"]),
        "is_author": tasks.is_author(meta, user["username"]),
        "is_executor": tasks.is_executor(meta, user["username"]),
        "can_respond": (
            meta["status"] == "active"
            and meta["author"] != user["username"]
            and not tasks.is_refused(meta, user["username"])
        ),
        "is_refused": tasks.is_refused(meta, user["username"]),
        "completion_req": meta["completion"].get("requested_by"),
    }
    return render_template("task.html", **ctx)


@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
@csrf_protect
def new_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        text = request.form.get("text", "")
        uploads = request.files.getlist("files")
        task_id, err = tasks.create_task(g.user["username"], title, text, uploads)
        if err:
            flash(err)
        else:
            return redirect(url_for("task_page", task_id=task_id))
    return render_template("task_form.html", task=None)


@app.route("/tasks/<task_id>/edit", methods=["GET", "POST"])
@login_required
@csrf_protect
def edit_task(task_id):
    meta = tasks.load_task(task_id)
    if not meta:
        abort(404)
    if meta["author"] != g.user["username"]:
        abort(403)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        text = request.form.get("text", "")
        uploads = request.files.getlist("files")
        delete_files = request.form.getlist("delete_files")
        err = tasks.update_task(task_id, g.user["username"], title, text, uploads, delete_files)
        if err:
            flash(err)
        else:
            return redirect(url_for("task_page", task_id=task_id))
    return render_template("task_form.html", task=meta)


@app.route("/tasks/<task_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_task(task_id):
    err = tasks.delete_task(task_id, g.user["username"])
    if err:
        flash(err)
    return redirect(url_for("index"))


@app.route("/tasks/<task_id>/files/<path:filename>")
@login_required
def download_file(task_id, filename):
    meta = tasks.load_task(task_id)
    if not meta:
        abort(404)
    base = os.path.join(tasks.task_dir(task_id), "files")
    safe = tasks._safe_filename(filename)
    if safe not in meta["files"]:
        abort(404)
    return send_from_directory(base, safe, as_attachment=True)


# ---------- task actions ----------

@app.route("/tasks/<task_id>/respond", methods=["POST"])
@login_required
@csrf_protect
def respond(task_id):
    err = tasks.respond(task_id, g.user["username"])
    if err:
        flash(err)
    return redirect(url_for("task_page", task_id=task_id))


@app.route("/tasks/<task_id>/refuse-executor", methods=["POST"])
@login_required
@csrf_protect
def refuse_executor(task_id):
    username = request.form.get("username", "").strip()
    reason = request.form.get("reason", "").strip()
    err = tasks.refuse_executor(task_id, g.user["username"], username, reason)
    if err:
        flash(err)
    return redirect(url_for("task_page", task_id=task_id))


@app.route("/tasks/<task_id>/refuse", methods=["POST"])
@login_required
@csrf_protect
def refuse_self(task_id):
    reason = request.form.get("reason", "").strip()
    err = tasks.refuse_self(task_id, g.user["username"], reason)
    if err:
        flash(err)
    return redirect(url_for("task_page", task_id=task_id))


@app.route("/tasks/<task_id>/complete-request", methods=["POST"])
@login_required
@csrf_protect
def complete_request(task_id):
    err = tasks.request_completion(task_id, g.user["username"])
    if err:
        flash(err)
    return redirect(url_for("task_page", task_id=task_id))


@app.route("/tasks/<task_id>/complete-respond", methods=["POST"])
@login_required
@csrf_protect
def complete_respond(task_id):
    action = request.form.get("action", "")
    err = tasks.respond_completion(task_id, g.user["username"], action)
    if err:
        flash(err)
    return redirect(url_for("task_page", task_id=task_id))


# ---------- profile ----------

@app.route("/u/<username>")
@login_required
def profile(username):
    user = db.get_user(username)
    if not user:
        abort(404)
    tab = request.args.get("tab", "inprogress")
    if tab not in ("inprogress", "completed", "posted"):
        tab = "inprogress"
    if tab == "inprogress":
        user_tasks = tasks.user_tasks(username, "executor", {"booked"})
    elif tab == "completed":
        user_tasks = tasks.user_tasks(username, "executor", {"completed"})
    else:
        user_tasks = tasks.user_tasks(username, "author", {"active", "booked", "completed"})
    is_self = g.user["username"] == username
    notifications = users.notifications_for(user["id"]) if is_self else []
    contacts = users.read_contacts(username)
    ctx = {
        "profile_user": user,
        "is_self": is_self,
        "contacts": contacts,
        "notifications": notifications,
        "tab": tab,
        "user_tasks": user_tasks,
        "avatar_url": url_for("user_avatar", username=username),
    }
    return render_template("profile.html", **ctx)


@app.route("/u/<username>/avatar")
def user_avatar(username):
    path = users.avatar_path(username)
    if path:
        return send_from_directory(users.user_folder(username), os.path.basename(path))
    svg = users.default_avatar_svg(username)
    return Response(svg, mimetype="image/svg+xml")


@app.route("/u/<username>/avatar", methods=["POST"])
@login_required
@csrf_protect
def upload_avatar(username):
    if username != g.user["username"]:
        abort(403)
    if request.form.get("delete") == "1":
        users.delete_avatar(username)
        flash("profile.avatar_deleted")
        return redirect(url_for("profile", username=username))
    err = users.save_avatar(username, request.files.get("avatar"))
    if err:
        flash(err)
    else:
        flash("profile.avatar_saved")
    return redirect(url_for("profile", username=username))


@app.route("/u/<username>/contacts/add", methods=["POST"])
@login_required
@csrf_protect
def add_contact(username):
    if username != g.user["username"]:
        abort(403)
    service = request.form.get("service", "").strip()
    contact = request.form.get("contact", "").strip()
    if service and contact and len(service) <= 100 and len(contact) <= 200:
        new_contact = {"service": service, "contact": contact}
        contacts = users.read_contacts(username)
        if not any(users.contacts_equal(c, new_contact) for c in contacts):
            contacts.append(new_contact)
            users.write_contacts(username, contacts)
            flash("profile.contact_added")
    else:
        flash("errors.contact_invalid")
    return redirect(url_for("profile", username=username))


@app.route("/u/<username>/contacts/remove", methods=["POST"])
@login_required
@csrf_protect
def remove_contact(username):
    if username != g.user["username"]:
        abort(403)
    service = request.form.get("service", "").strip()
    contact = request.form.get("contact", "").strip()
    contacts = users.read_contacts(username)
    contacts = [c for c in contacts if not (c["service"].lower() == service.lower() and c["contact"].lower() == contact.lower())]
    users.write_contacts(username, contacts)
    flash("profile.contact_removed")
    return redirect(url_for("profile", username=username))


# ---------- notifications ----------

@app.route("/notifications/mark-read", methods=["POST"])
@login_required
@csrf_protect
def notif_mark_read():
    nid = request.form.get("id", "")
    if nid.isdigit():
        users.mark_read(int(nid), g.user["id"])
    return redirect(url_for("profile", username=g.user["username"]))


@app.route("/notifications/mark-all-read", methods=["POST"])
@login_required
@csrf_protect
def notif_mark_all_read():
    users.mark_all_read(g.user["id"])
    return redirect(url_for("profile", username=g.user["username"]))


@app.route("/notifications/delete", methods=["POST"])
@login_required
@csrf_protect
def notif_delete():
    nid = request.form.get("id", "")
    if nid.isdigit():
        users.delete_notification(int(nid), g.user["id"])
    return redirect(url_for("profile", username=g.user["username"]))


# ---------- chat ----------

@app.route("/chat")
@login_required
def chat_list():
    convs = chat.conversations_for(g.user["id"])
    return render_template("chat.html", convs=convs)


@app.route("/chat/search")
@login_required
def chat_search():
    q = request.args.get("q", "").strip()
    me = g.user["id"]
    out = []
    for u in users.search_users(q):
        if u["id"] == me:
            continue
        has = chat.has_conversation(me, u["id"])
        unread = 0
        if has:
            conv_id = chat.get_or_create(me, u["id"])
            unread = chat.unread_count(conv_id, me)
        out.append({"username": u["username"], "has_chat": has, "unread": unread})
    out.sort(key=lambda x: (not x["has_chat"], x["username"].lower()))
    return {"users": out}


def _conv_with(username):
    user = db.get_user(username)
    if not user:
        return None, None
    me = g.user["id"]
    if user["id"] == me:
        return None, None
    conv_id = chat.get_or_create(me, user["id"])
    return conv_id, user


@app.route("/chat/<username>", methods=["GET", "POST"])
@login_required
def chat_conversation(username):
    conv_id, user = _conv_with(username)
    if not conv_id or not user:
        abort(404)
    conv = chat.conversation(conv_id)
    if not chat.is_participant(conv, g.user["id"]):
        abort(403)
    if request.method == "POST":
        body = request.form.get("body", "")
        file_storage = request.files.get("attachment")
        msg_id, err = chat.send(conv_id, g.user["id"], body, file_storage)
        xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if err:
            if xhr:
                return {"error": i18n.translate(get_lang(), err)}
            flash(err)
        else:
            chat.mark_read(conv_id, g.user["id"])
            other_name = user["username"]
            other_id = db.get_user_id(other_name)
            if other_id:
                preview = (body or "📎")[:80]
                users.add_notification(other_id, "notify.message", user=g.user["username"], body=preview)
            if xhr:
                new_msg = chat.new_messages(conv_id, msg_id - 1)
                m = [x for x in new_msg if x["id"] == msg_id]
                if not m:
                    return {"error": "reload"}
                m = m[0]
                return {"message": {
                    "id": m["id"],
                    "sender": m["sender_name"],
                    "mine": True,
                    "body": m["body"],
                    "attachment": m["attachment"],
                    "time": (m["created_at"] or "").replace("T", " ")[:16],
                }}
        return redirect(url_for("chat_conversation", username=username))
    chat.mark_read(conv_id, g.user["id"])
    users.mark_message_notifications_read(g.user["id"], user["username"])
    msgs = chat.messages(conv_id)
    for m in msgs:
        m["mine"] = m["sender_id"] == g.user["id"]
    return render_template(
        "conversation.html",
        other_user=user,
        messages=msgs,
        conversation_id=conv_id,
        last_msg_id=msgs[-1]["id"] if msgs else 0,
    )


@app.route("/chat/<username>/poll")
@login_required
def chat_poll(username):
    conv_id, _ = _conv_with(username)
    if not conv_id:
        return {"messages": []}
    conv = chat.conversation(conv_id)
    if not chat.is_participant(conv, g.user["id"]):
        abort(403)
    after = request.args.get("after", "0")
    try:
        after_id = int(after)
    except ValueError:
        after_id = 0
    out = []
    for m in chat.new_messages(conv_id, after_id):
        m["mine"] = m["sender_id"] == g.user["id"]
        m["time"] = (m["created_at"] or "").replace("T", " ")[:16]
        name = m.pop("sender_name", "")
        out.append({
            "id": m["id"],
            "sender": name,
            "mine": m["mine"],
            "body": m["body"],
            "attachment": m["attachment"],
            "time": m["time"],
        })
    return {"messages": out}


@app.route("/chat/<username>/attachment/<name>")
@login_required
def chat_attachment(username, name):
    conv_id, _ = _conv_with(username)
    if not conv_id:
        abort(404)
    conv = chat.conversation(conv_id)
    if not chat.is_participant(conv, g.user["id"]):
        abort(403)
    path = chat.attachment_path(conv_id, name)
    if not path:
        abort(404)
    return send_from_directory(chat.conv_files_dir(conv_id), os.path.basename(path), as_attachment=True)


def bootstrap():
    db.init_db()
    os.makedirs(os.path.join(BASE, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "u"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "chat_files"), exist_ok=True)
    auth.purge_expired_sessions()


bootstrap()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)