(function () {
  // Dentro da janela nativa (pywebview/WebView2), um <a href> para um arquivo não abre o
  // diálogo "Salvar como" do Windows sozinho — por isso os botões de download chamam a API
  // Python exposta (window.pywebview.api.*) quando disponível. Rodando num navegador comum
  // (modo de contingência do launcher.py, sem WebView2), isso fica indisponível e os links
  // funcionam do jeito normal do navegador.
  var pywebviewReady = false;
  window.addEventListener("pywebviewready", function () {
    pywebviewReady = true;
  });

  function hasNativeApi() {
    return pywebviewReady && window.pywebview && window.pywebview.api;
  }

  var themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var root = document.documentElement;
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("tubefetch-theme", next);
      } catch (e) {
        /* localStorage indisponível — o tema só não persiste entre sessões. */
      }
    });
  }

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
  var skippedWrap = document.getElementById("job-skipped-wrap");
  var skippedList = document.getElementById("job-skipped");
  var jobFilesDest = document.getElementById("job-files-dest");
  var destDirField = document.getElementById("dest-dir-field");
  var destDirDisplay = document.getElementById("dest-dir-display");
  var destDirValue = document.getElementById("dest-dir-value");
  var destDirChoose = document.getElementById("dest-dir-choose");
  var jobFormError = document.getElementById("job-form-error");
  var jobFormErrorMsg = document.getElementById("job-form-error-msg");
  var jobFormErrorDismiss = document.getElementById("job-form-error-dismiss");
  if (!form || !panel) return;

  function updateDestDirVisibility() {
    if (destDirField) destDirField.classList.toggle("hidden", !hasNativeApi());
  }
  window.addEventListener("pywebviewready", updateDestDirVisibility);
  updateDestDirVisibility();

  if (destDirChoose) {
    destDirChoose.addEventListener("click", function () {
      if (!hasNativeApi()) return;
      var originalText = destDirChoose.textContent;
      destDirChoose.disabled = true;
      destDirChoose.textContent = "Abrindo…";
      window.pywebview.api
        .choose_download_dir()
        .then(function (result) {
          destDirChoose.disabled = false;
          destDirChoose.textContent = originalText;
          if (result && result.ok && result.path) {
            destDirValue.value = result.path;
            if (destDirDisplay) {
              destDirDisplay.textContent = result.path;
              destDirDisplay.classList.add("chosen");
            }
          }
        })
        .catch(function (e) {
          destDirChoose.disabled = false;
          destDirChoose.textContent = originalText;
          setJobError(String((e && e.message) || e));
        });
    });
  }

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

  function saveViaNativeApi(button, apiCall, busyText) {
    var originalText = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    apiCall()
      .then(function (result) {
        button.disabled = false;
        if (result && result.ok) {
          button.textContent = "Salvo em: " + result.path.split(/[\\/]/).pop();
          setTimeout(function () {
            button.textContent = originalText;
          }, 3000);
        } else {
          button.textContent = originalText;
          if (result && result.error) setJobError(result.error);
        }
      })
      .catch(function (e) {
        button.disabled = false;
        button.textContent = originalText;
        setJobError(String(e.message || e));
      });
  }

  function renderFiles(id, token, files, destDir) {
    if (!filesList || !filesWrap) return;
    filesList.innerHTML = "";
    if (!files || files.length === 0) {
      filesWrap.classList.add("hidden");
      if (jobFilesDest) jobFilesDest.classList.add("hidden");
      return;
    }
    filesWrap.classList.remove("hidden");

    if (destDir) {
      // Já foram baixados direto na pasta escolhida — não tem "Salvar" nem zip pra fazer,
      // é só a conferência de que os arquivos estão lá.
      files.forEach(function (f) {
        var li = document.createElement("li");
        li.className = "file-row";
        var name = document.createElement("span");
        name.className = "file-name";
        name.textContent = f.name;
        var right = document.createElement("span");
        right.className = "file-size";
        right.textContent = humanSize(f.size);
        li.appendChild(name);
        li.appendChild(right);
        filesList.appendChild(li);
      });
      if (zipLink) zipLink.classList.add("hidden");
      if (jobFilesDest) {
        jobFilesDest.textContent = "Salvo em: " + destDir;
        jobFilesDest.classList.remove("hidden");
      }
      return;
    }

    if (jobFilesDest) jobFilesDest.classList.add("hidden");

    files.forEach(function (f) {
      var li = document.createElement("li");
      li.className = "file-row";
      var name = document.createElement("span");
      name.className = "file-name";
      name.textContent = f.name;
      var right = document.createElement("span");
      right.className = "file-size";

      if (hasNativeApi()) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn ghost sm";
        btn.textContent = "Salvar (" + humanSize(f.size) + ")";
        btn.addEventListener("click", function () {
          saveViaNativeApi(
            btn,
            function () {
              return window.pywebview.api.save_job_file(id, token, f.name);
            },
            "Salvando…"
          );
        });
        right.appendChild(btn);
      } else {
        var link = document.createElement("a");
        link.className = "btn ghost sm";
        link.textContent = "Baixar (" + humanSize(f.size) + ")";
        link.href = "/jobs/" + encodeURIComponent(id) + "/files/" + encodeURIComponent(f.name) + "?token=" + encodeURIComponent(token);
        right.appendChild(link);
      }

      li.appendChild(name);
      li.appendChild(right);
      filesList.appendChild(li);
    });

    if (zipLink) {
      if (files.length > 1) {
        zipLink.classList.remove("hidden");
        if (hasNativeApi()) {
          zipLink.removeAttribute("href");
          zipLink.onclick = function (ev) {
            ev.preventDefault();
            saveViaNativeApi(
              zipLink,
              function () {
                return window.pywebview.api.save_job_zip(id, token);
              },
              "Salvando…"
            );
          };
        } else {
          zipLink.onclick = null;
          zipLink.href = "/jobs/" + encodeURIComponent(id) + "/zip?token=" + encodeURIComponent(token);
        }
      } else {
        zipLink.classList.add("hidden");
      }
    }
  }

  function renderSkipped(skipped) {
    if (!skippedList || !skippedWrap) return;
    skippedList.innerHTML = "";
    if (!skipped || skipped.length === 0) {
      skippedWrap.classList.add("hidden");
      return;
    }
    skippedWrap.classList.remove("hidden");
    skipped.forEach(function (s) {
      var li = document.createElement("li");
      li.className = "skipped-row";

      var badge = document.createElement("span");
      badge.className = "skipped-id";
      badge.textContent = s.index ? "#" + s.index : "Aviso";
      li.appendChild(badge);

      var main = document.createElement("span");
      main.className = "skipped-main";

      if (s.title || s.id) {
        var titleEl = document.createElement(s.url ? "a" : "span");
        if (s.url) {
          titleEl.href = s.url;
          titleEl.target = "_blank";
          titleEl.rel = "noopener";
        }
        titleEl.className = "skipped-title";
        titleEl.textContent = s.title || s.id;
        main.appendChild(titleEl);
      }

      var reason = document.createElement("span");
      reason.className = "skipped-reason";
      reason.textContent = s.reason;
      main.appendChild(reason);

      li.appendChild(main);
      skippedList.appendChild(li);
    });
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
        renderFiles(data.id, token, data.files, data.dest_dir);
        renderSkipped(data.skipped);
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
        if (skippedWrap) skippedWrap.classList.add("hidden");
        if (jobFilesDest) jobFilesDest.classList.add("hidden");
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
