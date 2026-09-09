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
})();