const profileEl = document.getElementById("profile");
const suiteEl = document.getElementById("suite");
const targetUrlEl = document.getElementById("targetUrl");
const runForm = document.getElementById("runForm");
const runBtn = document.getElementById("runBtn");
const metaEl = document.getElementById("meta");
const summaryEl = document.getElementById("summary");
const summaryStatus = document.getElementById("summaryStatus");
const summaryCounts = document.getElementById("summaryCounts");
const reportLink = document.getElementById("reportLink");
const statusLine = document.getElementById("statusLine");
const errorBox = document.getElementById("errorBox");
const rowsEl = document.getElementById("rows");

let pollTimer = null;

function fmtDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  if (sec < 1) return `${Math.round(sec * 1000)} ms`;
  return `${sec.toFixed(2)} s`;
}

function setBusy(busy) {
  runBtn.disabled = busy;
  runBtn.textContent = busy ? "Running…" : "Run check";
  targetUrlEl.disabled = busy;
  suiteEl.disabled = busy;
  syncProfileEnabled();
  if (busy) {
    profileEl.disabled = true;
  }
}

function syncProfileEnabled() {
  const hasLink = Boolean((targetUrlEl.value || "").trim());
  profileEl.disabled = hasLink || runBtn.disabled;
}

function showError(message) {
  if (!message) {
    errorBox.hidden = true;
    errorBox.textContent = "";
    return;
  }
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function renderRows(tests) {
  if (!tests || !tests.length) {
    rowsEl.innerHTML =
      '<tr class="empty"><td colspan="5">No test rows yet.</td></tr>';
    return;
  }
  rowsEl.innerHTML = tests
    .map((t) => {
      const result = t.result || "unknown";
      return `<tr>
        <td><span class="pill ${result}">${result}</span></td>
        <td>${escapeHtml(t.title || t.id || t.nodeid || "")}</td>
        <td class="mono">${escapeHtml(t.expected || "—")}</td>
        <td class="mono">${escapeHtml(t.actual || "—")}</td>
        <td>${fmtDuration(t.duration_sec)}</td>
      </tr>`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderRun(run) {
  metaEl.hidden = false;
  metaEl.textContent = [
    run.target_url ? `Pasted link: ${run.target_url}` : `Profile: ${run.profile}`,
    run.health_url ? `Health URL: ${run.health_url}` : null,
    run.using_example_targets ? "Using example targets (DEV-LAB)" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  summaryEl.hidden = false;
  summaryStatus.className = "summary-status";
  if (run.status === "running" || run.status === "queued") {
    summaryStatus.textContent = "Running checks…";
    summaryStatus.classList.add("busy");
    summaryCounts.textContent = "This usually takes under a minute for smoke.";
    reportLink.hidden = true;
  } else if (run.status === "passed") {
    summaryStatus.textContent = "All passed";
    summaryStatus.classList.add("ok");
    summaryCounts.textContent = `${run.passed} passed · ${run.failed} failed · ${run.skipped} skipped · ${fmtDuration(run.duration_sec)}`;
  } else if (run.status === "failed") {
    summaryStatus.textContent = "Failed";
    summaryStatus.classList.add("bad");
    summaryCounts.textContent = `${run.passed} passed · ${run.failed} failed · ${run.skipped} skipped · ${fmtDuration(run.duration_sec)}`;
  } else {
    summaryStatus.textContent = "Error";
    summaryStatus.classList.add("bad");
    summaryCounts.textContent = run.error || "The check could not finish.";
  }

  if (run.report_url && (run.status === "passed" || run.status === "failed")) {
    reportLink.hidden = false;
    reportLink.href = run.report_url;
  } else {
    reportLink.hidden = true;
  }

  statusLine.hidden = false;
  statusLine.textContent = `Run ${run.id} · ${run.suite} · ${run.status}`;
  showError(run.error || "");
  renderRows(run.tests);
}

async function loadProfiles() {
  const res = await fetch("/api/profiles");
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const data = await res.json();
  profileEl.innerHTML = "";
  for (const p of data.profiles || []) {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.description
      ? `${p.name} — ${p.description}`
      : p.name;
    profileEl.appendChild(opt);
  }
  if (!profileEl.options.length) {
    throw new Error("No profiles found in targets YAML.");
  }
  syncProfileEnabled();
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollRun(runId) {
  const res = await fetch(`/api/runs/${runId}`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const run = await res.json();
  renderRun(run);
  if (run.status === "passed" || run.status === "failed" || run.status === "error") {
    stopPolling();
    setBusy(false);
  }
}

async function startRun() {
  showError("");
  const pasted = (targetUrlEl.value || "").trim();
  if (!pasted && !profileEl.value) {
    showError("Paste a site link or choose a profile.");
    return;
  }

  setBusy(true);
  stopPolling();
  rowsEl.innerHTML =
    '<tr class="empty"><td colspan="5">Running…</td></tr>';

  // Pasted link always wins over the profile dropdown.
  const payload = { suite: suiteEl.value };
  if (pasted) {
    payload.target_url = pasted;
  } else {
    payload.profile = profileEl.value;
  }

  const res = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch (_) {
      /* keep text */
    }
    setBusy(false);
    showError(detail);
    return;
  }

  const run = await res.json();
  renderRun(run);
  pollTimer = setInterval(() => {
    pollRun(run.id).catch((err) => {
      stopPolling();
      setBusy(false);
      showError(String(err.message || err));
    });
  }, 1500);
}

runForm.addEventListener("submit", (event) => {
  event.preventDefault();
  startRun().catch((err) => {
    setBusy(false);
    showError(String(err.message || err));
  });
});

targetUrlEl.addEventListener("input", syncProfileEnabled);

loadProfiles().catch((err) => {
  showError(`Could not load profiles: ${err.message || err}`);
});
