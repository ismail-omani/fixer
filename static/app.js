(function () {
  var dropzone = document.getElementById("dropzone");
  if (dropzone) {
    var input = document.getElementById("file-input");
    var list = dropzone.querySelector(".file-list");

    function render() {
      list.innerHTML = "";
      for (var i = 0; i < input.files.length; i++) {
        var d = document.createElement("div");
        d.textContent = "📎 " + input.files[i].name;
        list.appendChild(d);
      }
    }

    dropzone.addEventListener("click", function () { input.click(); });
    input.addEventListener("change", render);

    ["dragenter", "dragover"].forEach(function (ev) {
      dropzone.addEventListener(ev, function (e) {
        e.preventDefault();
        dropzone.classList.add("drag");
      });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dropzone.addEventListener(ev, function (e) {
        e.preventDefault();
        dropzone.classList.remove("drag");
      });
    });
    dropzone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        render();
      }
    });
  }

  var rowsWrap = document.getElementById("contact-rows");
  if (rowsWrap) {
    function rowCount() { return rowsWrap.querySelectorAll(".contact-row").length; }

    function refresh() {
      var rows = rowsWrap.querySelectorAll(".contact-row");
      for (var i = 0; i < rows.length; i++) {
        var isFirst = i === 0;
        rows[i].querySelector(".minus").classList.toggle("hidden", isFirst);
        rows[i].querySelector(".plus").classList.toggle("hidden", !isFirst);
      }
    }

    rowsWrap.addEventListener("click", function (e) {
      var t = e.target;
      if (t.classList.contains("plus")) {
        var row = rowsWrap.querySelector(".contact-row");
        var clone = row.cloneNode(true);
        clone.querySelectorAll("input").forEach(function (i) { i.value = ""; i.required = false; });
        rowsWrap.appendChild(clone);
        refresh();
      } else if (t.classList.contains("minus")) {
        t.closest(".contact-row").remove();
        refresh();
      }
    });

    refresh();
  }

  // ---------- theme + hamburger menu ----------
  var THEME_KEY = "fixer-theme";
  var themeBtn = document.getElementById("theme-toggle");
  var menuBtn = document.getElementById("menu-btn");
  var menu = document.getElementById("menu");

  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    updateThemeBtn();
  }

  function updateThemeBtn() {
    if (!themeBtn) return;
    var label = themeBtn.getAttribute("data-label") || "Theme";
    themeBtn.textContent = label + (currentTheme() === "dark" ? " ☀️" : " 🌙");
  }

  if (menuBtn && menu) {
    menuBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.classList.toggle("open");
    });
    document.addEventListener("click", function () {
      menu.classList.remove("open");
    });
    if (themeBtn) {
      themeBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        setTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }
  }
  updateThemeBtn();

  // ---------- user search on /chat ----------
  var chatListPage = document.getElementById("chat-list-page");
  if (chatListPage) {
    var userSearch = document.getElementById("user-search");
    var userResults = document.getElementById("user-results");
    var chatConvs = document.getElementById("chat-convs");
    var LBL_EXIST = chatListPage.getAttribute("data-existing") || "chat";
    var LBL_SEND = chatListPage.getAttribute("data-send") || "Message";
    var LBL_NONE = chatListPage.getAttribute("data-nofound") || "No users found";
    var searchTimer = null;

    function esc(s) {
      var d = document.createElement("div");
      d.textContent = s == null ? "" : String(s);
      return d.innerHTML;
    }

    function renderUsers(users) {
      userResults.innerHTML = "";
      if (!users.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = LBL_NONE;
        userResults.appendChild(p);
        return;
      }
      users.forEach(function (u) {
        var a = document.createElement("a");
        a.className = "user-row" + (u.has_chat && u.unread ? " has-unread" : "");
        a.href = "/chat/" + encodeURIComponent(u.username);
        var name = document.createElement("span");
        name.className = "chat-name";
        name.appendChild(document.createTextNode(u.username));
        if (u.unread) {
          var b = document.createElement("span");
          b.className = "badge";
          b.textContent = u.unread;
          name.appendChild(b);
        }
        a.appendChild(name);
        var tag = document.createElement("span");
        tag.className = u.has_chat ? "tag existing" : "tag new";
        tag.textContent = u.has_chat ? LBL_EXIST : LBL_SEND;
        a.appendChild(tag);
        userResults.appendChild(a);
      });
    }

    userSearch.addEventListener("input", function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        var q = userSearch.value.trim();
        if (!q) {
          userResults.innerHTML = "";
          chatConvs.hidden = false;
          return;
        }
        chatConvs.hidden = true;
        fetch("/chat/search?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data && data.users) renderUsers(data.users);
          })
          .catch(function () {});
      }, 250);
    });
  }

  // ---------- live task dashboard (poll every 5s) ----------
  var taskFeed = document.getElementById("task-feed");
  if (taskFeed) {
    var feedMode = taskFeed.getAttribute("data-mode") || "active";
    function pollFeed() {
      var qEl = document.querySelector(".search input[name=q]");
      var q = qEl ? qEl.value.trim() : "";
      fetch("/feed?mode=" + encodeURIComponent(feedMode) + "&q=" + encodeURIComponent(q))
        .then(function (r) { return r.text(); })
        .then(function (html) {
          if (taskFeed.innerHTML !== html) taskFeed.innerHTML = html;
        })
        .catch(function () {});
      setTimeout(pollFeed, 5000);
    }
    setTimeout(pollFeed, 5000);
  }

  // ---------- chat conversation ----------
  var chatPage = document.querySelector(".chat-page");
  if (chatPage) {
    var thread = document.getElementById("chat-thread");
    var form = document.getElementById("chat-form");
    var bodyInput = document.getElementById("chat-body");
    var fileInput = document.getElementById("chat-file");
    var fileChip = document.getElementById("chat-file-chip");
    var fileName = document.getElementById("chat-file-name");
    var fileClear = document.getElementById("chat-file-clear");
    var chatErr = document.getElementById("chat-err");
    var other = chatPage.getAttribute("data-other");
    var lastId = parseInt(chatPage.getAttribute("data-last") || "0", 10);
    var csrf = chatPage.getAttribute("data-csrf");
    var atBottom = true;

    function esc(s) {
      var d = document.createElement("div");
      d.textContent = s == null ? "" : String(s);
      return d.innerHTML;
    }

    function scrollToBottom(smooth) {
      thread.scrollTo({ top: thread.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    }

    thread.addEventListener("scroll", function () {
      atBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 60;
    });

    function showErr(msg) {
      if (!chatErr) return;
      chatErr.textContent = msg;
      chatErr.hidden = false;
      clearTimeout(chatErr._t);
      chatErr._t = setTimeout(function () { chatErr.hidden = true; }, 5000);
    }

    function updateChip() {
      if (fileInput.files.length) {
        fileName.textContent = fileInput.files[0].name;
        fileChip.hidden = false;
      } else {
        fileChip.hidden = true;
        fileName.textContent = "";
      }
    }

    function clearComposer() {
      bodyInput.value = "";
      fileInput.value = "";
      updateChip();
    }

    if (fileInput) {
      fileInput.addEventListener("change", updateChip);
    }
    if (fileClear) {
      fileClear.addEventListener("click", function () {
        fileInput.value = "";
        updateChip();
      });
    }

    // Enter = send, Shift+Enter = newline
    bodyInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        form.requestSubmit();
      }
    });

    function addMessage(m, bump) {
      if (document.getElementById("msg-" + m.id)) return;
      var wrap = document.createElement("div");
      wrap.className = "msg " + (m.mine ? "mine" : "");
      wrap.id = "msg-" + m.id;
      var bubble = document.createElement("div");
      bubble.className = "bubble";
      var body = document.createElement("div");
      body.className = "msg-body";
      body.textContent = m.body || "";
      bubble.appendChild(body);
      if (m.attachment) {
        var f = document.createElement("div");
        f.className = "msg-file";
        var a = document.createElement("a");
        a.href = "/chat/" + encodeURIComponent(other) + "/attachment/" + encodeURIComponent(m.attachment.split("/").pop());
        a.textContent = "📎 " + m.attachment.split("/").pop();
        a.setAttribute("download", "");
        f.appendChild(a);
        bubble.appendChild(f);
      }
      var time = document.createElement("div");
      time.className = "msg-time";
      time.textContent = m.time || "";
      bubble.appendChild(time);
      wrap.appendChild(bubble);
      thread.appendChild(wrap);
      if (m.id > lastId) lastId = m.id;
      if (bump && atBottom) scrollToBottom(true);
    }

    window.chatInitMessages = function (msgs) {
      for (var i = 0; i < msgs.length; i++) addMessage(msgs[i], false);
      scrollToBottom(false);
    };

    window.chatPoll = function () {
      fetch("/chat/" + encodeURIComponent(other) + "/poll?after=" + lastId)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.messages) {
            for (var i = 0; i < data.messages.length; i++) addMessage(data.messages[i], true);
          }
        })
        .catch(function () {});
      setTimeout(window.chatPoll, 3000);
    };

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var savedBody = bodyInput.value;
        var fd = new FormData();
        fd.append("csrf", csrf);
        fd.append("body", savedBody);
        if (fileInput && fileInput.files.length) fd.append("attachment", fileInput.files[0]);
        clearComposer();
        var btn = form.querySelector("button[type=submit]");
        if (btn) btn.disabled = true;
        fetch(form.action, { method: "POST", body: fd })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            btn.disabled = false;
            if (data && data.message) {
              addMessage(data.message, true);
            } else if (data && data.error && data.error !== "reload") {
              bodyInput.value = savedBody;
              showErr(data.error);
            } else {
              window.location.reload();
            }
          })
          .catch(function () {
            btn.disabled = false;
            bodyInput.value = savedBody;
            window.location.reload();
          });
      });
    }

    scrollToBottom(false);
    setTimeout(window.chatPoll, 3000);
  }
})();