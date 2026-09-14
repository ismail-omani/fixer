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

  var chatPage = document.querySelector(".chat-page");
  if (chatPage) {
    var thread = document.getElementById("chat-thread");
    var form = document.getElementById("chat-form");
    var bodyInput = document.getElementById("chat-body");
    var fileInput = document.getElementById("chat-file");
    var fileName = document.getElementById("chat-file-name");
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

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        fileName.textContent = fileInput.files.length ? "📎 " + fileInput.files[0].name : "";
      });
    }

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fd = new FormData();
        fd.append("csrf", csrf);
        fd.append("body", bodyInput.value);
        if (fileInput && fileInput.files.length) fd.append("attachment", fileInput.files[0]);
        var btn = form.querySelector("button[type=submit]");
        if (btn) btn.disabled = true;
        fetch(form.action, { method: "POST", body: fd })
          .then(function (r) {
            if (r.ok) return r.json().catch(function () { return { error: "reload" }; });
            return { error: "reload" };
          })
          .then(function (data) {
            btn.disabled = false;
            if (data && data.message) {
              addMessage(data.message, true);
              bodyInput.value = "";
              fileInput.value = "";
              fileName.textContent = "";
            } else {
              window.location.reload();
            }
          })
          .catch(function () {
            btn.disabled = false;
            window.location.reload();
          });
      });
    }

    scrollToBottom(false);
    setTimeout(window.chatPoll, 3000);
  }
})();