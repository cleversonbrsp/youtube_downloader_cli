(function () {
  var el = document.getElementById("svc-status");
  if (el) {
    fetch("/api/health", { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (!r.ok) throw new Error("status " + r.status);
        return r.json();
      })
      .then(function (data) {
        var ok = data.status === "ok";
        el.textContent = ok ? "Serviço online" : "Resposta inesperada";
        el.dataset.state = ok ? "ok" : "err";
      })
      .catch(function () {
        el.textContent = "Indisponível";
        el.dataset.state = "err";
      });
  }

  var modeInputs = document.querySelectorAll('input[name="mode"]');
  var subtitleFields = document.getElementById("subtitle-fields");

  function currentMode() {
    for (var i = 0; i < modeInputs.length; i++) {
      if (modeInputs[i].checked) return modeInputs[i].value;
    }
    return null;
  }

  function toggleSubtitleFields() {
    if (!subtitleFields) return;
    subtitleFields.classList.toggle("hidden", currentMode() !== "subtitles");
  }
  modeInputs.forEach(function (input) {
    input.addEventListener("change", toggleSubtitleFields);
  });
  toggleSubtitleFields();

  var form = document.getElementById("job-form");
  var panel = document.getElementById("job-panel");
  var panelEmpty = document.getElementById("job-panel-empty");
  var submitBtn = document.getElementById("job-submit");
  var submitHint = document.getElementById("job-submit-hint");
  var jobIdEl = document.getElementById("job-id");
  var statusPill = document.getElementById("job-status-pill");
  var logBox = document.getElementById("job-log");
  var filesWrap = document.getElementById("job-files-wrap");
  var filesList = document.getElementById("job-files");
  var zipLink = document.getElementById("job-zip-link");
  var jobFormError = document.getElementById("job-form-error");
  var jobFormErrorMsg = document.getElementById("job-form-error-msg");
  var jobFormErrorDismiss = document.getElementById("job-form-error-dismiss");
  if (!form || !panel) return;

  var pollTimer = null;

  function clearJobError() {
    if (jobFormError) jobFormError.classList.add("hidden");
    if (jobFormErrorMsg) jobFormErrorMsg.textContent = "";
  }

  function setJobError(msg) {
    if (jobFormErrorMsg) jobFormErrorMsg.textContent = msg;
    if (jobFormError) jobFormError.classList.remove("hidden");
  }

  if (jobFormErrorDismiss) {
    jobFormErrorDismiss.addEventListener("click", clearJobError);
  }

  function showPanel() {
    panel.classList.remove("hidden");
    if (panelEmpty) {
      panelEmpty.classList.add("hidden");
      panelEmpty.setAttribute("aria-hidden", "true");
    }
  }

  var STATUS_LABELS = {
    queued: "Na fila",
    running: "Baixando…",
    completed: "Concluído",
    failed: "Falhou",
    erro: "Erro",
  };

  function setStatus(apiStatus) {
    statusPill.dataset.state = apiStatus;
    statusPill.textContent = STATUS_LABELS[apiStatus] || apiStatus;
  }

  function humanSize(bytes) {
    if (!bytes && bytes !== 0) return "";
    var units = ["B", "KB", "MB", "GB"];
    var i = 0;
    var v = bytes;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    return v.toFixed(v >= 10 || i === 0 ? 0 : 1) + " " + units[i];
  }

  function renderFiles(id, token, files) {
    if (!filesList || !filesWrap) return;
    filesList.innerHTML = "";
    if (!files || files.length === 0) {
      filesWrap.classList.add("hidden");
      return;
    }
    filesWrap.classList.remove("hidden");
    files.forEach(function (f) {
      var li = document.createElement("li");
      li.className = "file-row";
      var name = document.createElement("span");
      name.className = "file-name";
      name.textContent = f.name;
      var right = document.createElement("span");
      right.className = "file-size";
      var link = document.createElement("a");
      link.className = "btn ghost sm";
      link.textContent = "Baixar (" + humanSize(f.size) + ")";
      link.href = "/jobs/" + encodeURIComponent(id) + "/files/" + encodeURIComponent(f.name) + "?token=" + encodeURIComponent(token);
      right.appendChild(link);
      li.appendChild(name);
      li.appendChild(right);
      filesList.appendChild(li);
    });
    if (zipLink) {
      if (files.length > 1) {
        zipLink.href = "/jobs/" + encodeURIComponent(id) + "/zip?token=" + encodeURIComponent(token);
        zipLink.classList.remove("hidden");
      } else {
        zipLink.classList.add("hidden");
      }
    }
  }

  function pollJob(id, token) {
    var url = "/api/jobs/" + encodeURIComponent(id) + "?token=" + encodeURIComponent(token);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.error || r.status);
          return body;
        });
      })
      .then(function (data) {
        jobIdEl.textContent = data.id;
        setStatus(data.status);
        logBox.textContent = data.log || "(aguardando saída…)";
        logBox.scrollTop = logBox.scrollHeight;
        renderFiles(data.id, token, data.files);
        if (data.status === "completed" || data.status === "failed") {
          if (pollTimer) clearInterval(pollTimer);
          pollTimer = null;
          submitBtn.disabled = false;
          if (data.status === "completed") {
            submitHint.textContent = "Concluído.";
          } else {
            submitHint.textContent = data.error || "Falhou.";
            setJobError(data.error || "O download falhou.");
          }
        }
      })
      .catch(function (e) {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null;
        submitBtn.disabled = false;
        var msg = String(e.message || e);
        submitHint.textContent = msg;
        setJobError(msg);
        setStatus("erro");
      });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    submitHint.textContent = "";
    clearJobError();

    var urlInput = form.querySelector('[name="url"]');
    if (!urlInput || !urlInput.value.trim()) {
      var vazio = "Informe a URL do vídeo ou playlist.";
      submitHint.textContent = vazio;
      setJobError(vazio);
      return;
    }

    submitBtn.disabled = true;

    var fd = new FormData(form);
    fetch("/api/jobs", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.error || "Erro " + r.status);
          return body;
        });
      })
      .then(function (data) {
        showPanel();
        jobIdEl.textContent = data.id;
        setStatus(data.status || "queued");
        logBox.textContent = "Aguardando saída…";
        if (filesWrap) filesWrap.classList.add("hidden");
        if (pollTimer) clearInterval(pollTimer);
        pollJob(data.id, data.token);
        pollTimer = setInterval(function () {
          pollJob(data.id, data.token);
        }, 2000);
      })
      .catch(function (e) {
        var msg = String(e.message || e);
        submitHint.textContent = msg;
        setJobError(msg);
        submitBtn.disabled = false;
      });
  });
})();
