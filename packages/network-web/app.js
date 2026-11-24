const profileEl = document.getElementById("profile");
const suiteEl = document.getElementById("suite");
const targetUrlEl = document.getElementById("targetUrl");
const runForm = document.getElementById("runForm");
const runBtn = document.getElementById("runBtn");
const runBtnSpinner = document.getElementById("runBtnSpinner");
const runBtnLabel = document.getElementById("runBtnLabel");
const loadingPanel = document.getElementById("loadingPanel");
const metaEl = document.getElementById("meta");
const summaryEl = document.getElementById("summary");
const summaryStatus = document.getElementById("summaryStatus");
const summaryCounts = document.getElementById("summaryCounts");
const summaryHint = document.getElementById("summaryHint");
const reportLink = document.getElementById("reportLink");
const statusLine = document.getElementById("statusLine");
const errorBox = document.getElementById("errorBox");
const rowsEl = document.getElementById("rows");

let pollTimer = null;

/** Plain-language copy for non-technical readers. Keyed by catalog id. */
const CASE_COPY = {
  NET_C01: {
    title: "Can we reach the site?",
    check: "Open a basic network connection to the site’s main address.",
    ok: "The site accepted the connection.",
    failHint: "The site or network path may be down, blocked, or mistyped. Ask IT to confirm the hostname and firewall.",
  },
  NET_C02: {
    title: "Is the secure web port open?",
    check: "Confirm the usual secure web port (HTTPS) answers.",
    ok: "The secure port is open and answering.",
    failHint: "HTTPS may be blocked or the server is not listening. Ask IT to check port 443.",
  },
  NET_C03: {
    title: "Do dead addresses time out safely?",
    check: "Try a known unreachable address and expect a clean timeout (not a hang).",
    ok: "The checker stopped on time instead of hanging.",
    failHint: "Timeouts may be misconfigured. Ask the technical team to review timeout settings.",
  },
  NET_C04: {
    title: "Is a wrong port properly closed?",
    check: "Try a port the site should not use and expect no connection.",
    ok: "The unused port stayed closed, as expected.",
    failHint: "An unexpected service may be exposed. Ask IT to review open ports.",
  },
  NET_D01: {
    title: "Does the site name resolve?",
    check: "Look up the site name in DNS (like a phone book for the internet).",
    ok: "The site name resolved to at least one address.",
    failHint: "DNS may be wrong or unavailable. Confirm the domain spelling and DNS settings.",
  },
  NET_D02: {
    title: "Do fake names correctly fail?",
    check: "Look up a name that must not exist and expect “not found.”",
    ok: "Fake names correctly failed DNS lookup.",
    failHint: "DNS error handling looks wrong. Ask the technical team to review resolver behavior.",
  },
  NET_D03: {
    title: "Are enough server addresses published?",
    check: "Confirm DNS returns the expected number of addresses.",
    ok: "DNS published enough addresses.",
    failHint: "Fewer addresses than expected. Ask DNS/CDN owners if a record is missing.",
  },
  NET_D04: {
    title: "Does a silent DNS server time out?",
    check: "Query a resolver that should not answer and expect a timeout.",
    ok: "The checker timed out cleanly on a silent DNS server.",
    failHint: "DNS timeout handling may be too slow. Ask the technical team to review it.",
  },
  NET_D05: {
    title: "Are DNS answers on the allowlist?",
    check: "Confirm the site only resolves to approved IP addresses.",
    ok: "All resolved addresses are on the approved list.",
    failHint: "The site resolved to an unexpected address (possible wrong cutover). Ask IT to verify DNS/CDN.",
  },
  NET_H01: {
    title: "Does the health page load over HTTPS?",
    check: "Open the site’s health/home page using a secure (HTTPS) connection.",
    ok: "The health page loaded securely with an acceptable status.",
    failHint: "The page did not return the expected success status, or did not stay on HTTPS. Ask the web team to check the URL and SSL.",
  },
  NET_H02: {
    title: "Is the security certificate working?",
    check: "Complete a secure TLS handshake with the server.",
    ok: "The secure connection negotiated successfully.",
    failHint: "Certificate or TLS setup may be broken. Ask IT to check the SSL certificate.",
  },
  NET_H03: {
    title: "Does insecure HTTP upgrade to HTTPS?",
    check: "Open the plain http:// link and follow redirects to https://.",
    ok: "Visitors are redirected to the secure https:// site.",
    failHint: "HTTP may not redirect to HTTPS. Ask the web team to enable HTTPS redirect.",
  },
  NET_H04: {
    title: "Are required response headers present?",
    check: "Confirm the page sends the headers your team configured as required.",
    ok: "All required headers were present.",
    failHint: "A required header is missing. Ask the web team to add it (for example Content-Type or security headers).",
  },
  NET_H05: {
    title: "Do missing pages return an error?",
    check: "Request a path that should not exist and expect a “not found” style error (4xx).",
    ok: "Missing pages correctly return a client error.",
    failHint:
      "The site answered “OK” for a missing path. Many marketing sites do this on purpose. Ask the technical team to set a real “not found” path in the config, or treat this as informational if every URL shows a page.",
  },
  NET_H06: {
    title: "Is the certificate still valid long enough?",
    check: "Check how many days remain before the SSL certificate expires.",
    ok: "The certificate has enough days left before expiry.",
    failHint: "The certificate will expire soon. Ask IT to renew it before visitors see browser warnings.",
  },
  NET_H07: {
    title: "Do security header values look right?",
    check: "Confirm important headers (such as HSTS) contain the expected text.",
    ok: "Header values matched what was configured.",
    failHint: "A security header is missing or weak. Ask the web team to strengthen headers (for example Strict-Transport-Security).",
  },
  NET_M01: {
    title: "Does mutual TLS (client certificate) work?",
    check: "Connect with a client certificate the gateway expects.",
    ok: "The client certificate was accepted.",
    failHint: "mTLS failed. Confirm the client certificate is installed on the allowed runner and still valid.",
  },
  NET_P01: {
    title: "Is the site fast enough?",
    check: "Time how long the health page takes and compare it to your speed budget.",
    ok: "The page responded within the allowed time.",
    failHint: "The site is slower than the agreed limit. Ask the web/ops team to investigate performance.",
  },
  NET_P02: {
    title: "Do soft timeouts stop hung calls?",
    check: "Call a blackhole address and expect the client to stop within the timeout.",
    ok: "Hung calls stop within the timeout budget.",
    failHint: "Timeouts may be too long. Ask the technical team to review client timeout settings.",
  },
  NET_P03: {
    title: "Are retries limited?",
    check: "Confirm failing operations only retry a fixed number of times.",
    ok: "Retries stayed within the safe limit.",
    failHint: "Retry logic may loop too much. Ask the technical team to review retry settings.",
  },
  NET_N01: {
    title: "Does HTTP send people to HTTPS?",
    check: "Call the plain HTTP URL without following redirects and check the Location header.",
    ok: "HTTP responds with a redirect to https://.",
    failHint: "HTTP is not clearly upgrading to HTTPS. Ask the web team to fix the redirect.",
  },
  NET_N02: {
    title: "Are bad certificates rejected?",
    check: "Try a known expired certificate host and expect a rejection.",
    ok: "Expired certificates are correctly rejected.",
    failHint: "Bad certificates may be accepted. Do not disable certificate checking.",
  },
  NET_N03: {
    title: "Do slow responses time out?",
    check: "Call a deliberately slow URL with a short timeout.",
    ok: "Slow responses timed out as expected.",
    failHint: "Slow responses may hang the client. Ask the technical team to review timeouts.",
  },
  NET_N04: {
    title: "Are name-mismatched certificates rejected?",
    check: "Try a host whose certificate does not match its name.",
    ok: "Mismatched certificates are correctly rejected.",
    failHint: "Certificate name checks may be weak. Keep verification enabled.",
  },
  overlay_endpoints_reachable: {
    title: "Are extra services reachable?",
    check: "Open connections to extra endpoints (CDN, API, gateway, webhook).",
    ok: "All configured extra endpoints accepted a connection.",
    failHint: "One or more extra services could not be reached. Ask IT which overlay failed.",
  },
};

function fmtDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  if (sec < 1) return `${Math.round(sec * 1000)} ms`;
  return `${sec.toFixed(2)} s`;
}

function setBusy(busy) {
  runBtn.disabled = busy;
  runBtnSpinner.hidden = !busy;
  runBtnLabel.textContent = busy ? "Running…" : "Run check";
  loadingPanel.hidden = !busy;
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function caseId(test) {
  return String(test.id || "").trim();
}

function copyFor(test) {
  const id = caseId(test);
  if (CASE_COPY[id]) return CASE_COPY[id];
  return {
    title: test.title || id || "Network check",
    check: test.expected || "Ran a network check.",
    ok: "Matched the expected result.",
    failHint: "Ask the technical team to review the technical details below.",
  };
}

function resultLabel(result) {
  if (result === "passed") return "Passed";
  if (result === "failed" || result === "error") return "Failed";
  if (result === "skipped") return "Skipped";
  return result || "Unknown";
}

function friendlyActual(test, copy) {
  const result = test.result || "";
  const actual = (test.actual || "").trim();
  if (result === "skipped") {
    return actual || "This check was skipped (not configured for this run).";
  }
  if (result === "passed") {
    return explainActual(actual, copy.ok);
  }
  if (result === "failed" || result === "error") {
    return explainActual(actual, "This check did not match what we expected.");
  }
  return actual || "—";
}

function explainActual(actual, fallback) {
  if (!actual || actual === "matched expected") return fallback;

  const status = actual.match(/status=(\d+)/i);
  const url = actual.match(/url=([^\s;]+)/i);
  const days = actual.match(/days_remaining=([\d.]+)/i);
  const protocol = actual.match(/protocol=([^\s;]+)/i);
  const open = actual.match(/open=(true|false)/i);
  const elapsed = actual.match(/elapsed_ms=([\d.]+)/i);

  const bits = [];
  if (status) {
    const code = Number(status[1]);
    if (code >= 200 && code < 300) bits.push(`The server answered OK (${code}).`);
    else if (code >= 300 && code < 400) bits.push(`The server sent a redirect (${code}).`);
    else if (code >= 400 && code < 500) bits.push(`The server reported a client error (${code}).`);
    else if (code >= 500) bits.push(`The server reported an error (${code}).`);
    else bits.push(`Status code was ${code}.`);
  }
  if (days) bits.push(`Certificate has about ${Math.floor(Number(days[1]))} days left.`);
  if (protocol) bits.push(`Secure protocol: ${protocol[1]}.`);
  if (open) {
    bits.push(open[1].toLowerCase() === "true" ? "Connection opened." : "Connection did not open.");
  }
  if (elapsed) bits.push(`Took about ${Math.round(Number(elapsed[1]))} ms.`);
  if (url && !status) bits.push(`URL: ${url[1]}`);

  if (bits.length) return bits.join(" ");
  return fallback;
}

function nextStep(test, copy) {
  const result = test.result || "";
  if (result === "failed" || result === "error") return copy.failHint;
  if (result === "skipped") {
    return "No action needed unless your technical team expected this check to run.";
  }
  return "";
}

function renderRows(tests) {
  if (!tests || !tests.length) {
    rowsEl.innerHTML =
      '<tr class="empty"><td colspan="4">No results yet. Run a check to see a plain-language report.</td></tr>';
    return;
  }
  rowsEl.innerHTML = tests
    .map((t) => {
      const result = t.result || "unknown";
      const copy = copyFor(t);
      const found = friendlyActual(t, copy);
      const tip = nextStep(t, copy);
      const techExpected = t.expected || "";
      const techActual = t.actual || "";
      const tipHtml = tip
        ? `<p class="row-tip"><span class="row-tip-label">${
            result === "failed" || result === "error" ? "What to do" : "Note"
          }</span> ${escapeHtml(tip)}</p>`
        : "";
      const detailsHtml =
        techExpected || techActual
          ? `<details class="tech">
              <summary>Technical details</summary>
              <p><strong>Expected:</strong> ${escapeHtml(techExpected || "—")}</p>
              <p><strong>Actual:</strong> ${escapeHtml(techActual || "—")}</p>
              <p><strong>Case ID:</strong> ${escapeHtml(caseId(t) || "—")}</p>
            </details>`
          : "";
      return `<tr class="row-${escapeHtml(result)}">
        <td>
          <span class="pill ${escapeHtml(result)}">${escapeHtml(resultLabel(result))}</span>
        </td>
        <td>
          <p class="row-title">${escapeHtml(copy.title)}</p>
          <p class="row-check">${escapeHtml(copy.check)}</p>
        </td>
        <td>
          <p class="row-found">${escapeHtml(found)}</p>
          ${tipHtml}
          ${detailsHtml}
        </td>
        <td class="row-duration">${escapeHtml(fmtDuration(t.duration_sec))}</td>
      </tr>`;
    })
    .join("");
}

function renderRun(run) {
  metaEl.hidden = false;
  metaEl.textContent = [
    run.target_url ? `Checked link: ${run.target_url}` : `Profile: ${run.profile}`,
    run.health_url ? `Health page: ${run.health_url}` : null,
    run.using_example_targets ? "Using sample lab targets (not your live product evidence)" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  summaryEl.hidden = false;
  summaryStatus.className = "summary-status";
  summaryHint.hidden = true;
  summaryHint.textContent = "";

  if (run.status === "running" || run.status === "queued") {
    summaryStatus.textContent = "Running checks…";
    summaryStatus.classList.add("busy");
    summaryCounts.textContent = "This usually takes under a minute for a quick (smoke) run.";
    reportLink.hidden = true;
  } else if (run.status === "passed") {
    summaryStatus.textContent = "All checks passed";
    summaryStatus.classList.add("ok");
    summaryCounts.textContent = `${run.passed} passed · ${run.failed} failed · ${run.skipped} skipped · ${fmtDuration(run.duration_sec)}`;
    summaryHint.hidden = false;
    summaryHint.textContent =
      "In plain terms: from this computer, the site could be reached securely within the time budget.";
  } else if (run.status === "failed") {
    summaryStatus.textContent = "Some checks failed";
    summaryStatus.classList.add("bad");
    summaryCounts.textContent = `${run.passed} passed · ${run.failed} failed · ${run.skipped} skipped · ${fmtDuration(run.duration_sec)}`;
    summaryHint.hidden = false;
    summaryHint.textContent =
      "Read the Failed rows below. Each one explains what we checked, what happened, and what to do next. Technical details are optional.";
  } else {
    summaryStatus.textContent = "Could not finish";
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
  statusLine.textContent = `Reference: run ${run.id} · ${run.suite} suite · ${run.status}`;
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
    '<tr class="empty"><td colspan="4">Waiting for results…</td></tr>';

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
