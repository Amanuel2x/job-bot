/**
 * Popup script — Settings UI and bot controls.
 * Saves/loads all config from chrome.storage.sync.
 * Communicates with service worker for bot start/stop/status.
 */

/* ───────── DOM references ───────── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const btnStart = $("#btnStart");
const btnPause = $("#btnPause");
const btnStop = $("#btnStop");
const btnSave = $("#btnSave");
const saveStatus = $("#saveStatus");
const statusBadge = $("#statusBadge");

// Stats
const statJobs = $("#statJobs");
const statApplied = $("#statApplied");
const statBlacklisted = $("#statBlacklisted");
const statAlready = $("#statAlready");
const statCannot = $("#statCannot");
const statSkipped = $("#statSkipped");
const statDuration = $("#statDuration");

// Export buttons
const btnExportCsv = $("#btnExportCsv");
const btnExportJson = $("#btnExportJson");
const btnClearResults = $("#btnClearResults");
const resultsLog = $("#resultsLog");

/* ───────── Helpers ───────── */

/**
 * Parse a comma-separated string into a trimmed array, filtering empties.
 */
function csvToArray(str) {
  if (!str) return [];
  return str.split(",").map((s) => s.trim()).filter(Boolean);
}

function arrayToCsv(arr) {
  if (!arr || arr.length === 0) return "";
  return arr.join(", ");
}

/**
 * Parse "Key: Value" lines into an object.
 */
function parseKeyValueLines(text) {
  const obj = {};
  if (!text) return obj;
  for (const line of text.split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.substring(0, idx).trim();
    const val = line.substring(idx + 1).trim();
    if (key) obj[key] = val;
  }
  return obj;
}

function keyValueToLines(obj) {
  if (!obj) return "";
  return Object.entries(obj)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

function getCheckedValues(name) {
  return $$(`input[name="${name}"]:checked`).map((cb) => cb.value);
}

function setCheckedValues(name, values) {
  const arr = values || [];
  $$(`input[name="${name}"]`).forEach((cb) => {
    cb.checked = arr.includes(cb.value);
  });
}

function formatDuration(ms) {
  const sec = Math.floor(ms / 1000);
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (min === 0) return `${sec}s`;
  return `${min}m ${remSec}s`;
}

/* ───────── Settings save/load ───────── */

function gatherSettings() {
  return {
    keywords: csvToArray($("#keywords").value),
    location: csvToArray($("#location").value),
    experienceLevels: getCheckedValues("experienceLevel"),
    datePosted: [$("#datePosted").value],
    jobType: getCheckedValues("jobType"),
    remote: getCheckedValues("remote"),
    salary: [$("#salary").value].filter(Boolean),
    sort: [$("#sort").value],

    // Filters
    blacklistCompanies: csvToArray($("#blacklistCompanies").value),
    blackListTitles: csvToArray($("#blackListTitles").value),
    onlyApplyCompanies: csvToArray($("#onlyApplyCompanies").value),
    onlyApplyTitles: csvToArray($("#onlyApplyTitles").value),
    blockHiringMember: csvToArray($("#blockHiringMember").value),
    onlyApplyHiringMember: csvToArray($("#onlyApplyHiringMember").value),
    onlyApplyMaxApplications: $("#onlyApplyMaxApplications").value || "0",
    onlyApplyMinApplications: $("#onlyApplyMinApplications").value || "0",
    onlyApplyJobDescription: csvToArray($("#onlyApplyJobDescription").value),
    blockJobDescription: csvToArray($("#blockJobDescription").value),

    // Form filling
    phoneNumber: $("#phoneNumber").value.trim(),
    preferredCv: parseInt($("#preferredCv").value, 10) || 1,
    defaultRadioOption: parseInt($("#defaultRadioOption").value, 10) || 0,
    answerAllCheckboxes: (() => {
      const v = $("#answerAllCheckboxes").value;
      if (v === "true") return true;
      if (v === "false") return false;
      return "";
    })(),
    additionalQuestions: parseKeyValueLines($("#additionalQuestionsText").value),

    // AI
    useAi: $("#useAi").checked,
    openaiApiKey: $("#openaiApiKey").value.trim(),
    openaiModel: $("#openaiModel").value,
    aiResumeContext: $("#aiResumeContext").value.trim(),

    // Advanced
    dryRun: $("#dryRun").checked,
    maxApplicationsPerRun: parseInt($("#maxApplicationsPerRun").value, 10) || 0,
    followCompanies: $("#followCompanies").checked,
    saveBeforeApply: $("#saveBeforeApply").checked,
    outputSkippedQuestions: $("#outputSkippedQuestions").checked,
    listNonEasyApplyJobsUrl: $("#listNonEasyApplyJobsUrl").checked,
  };
}

function populateSettings(s) {
  if (!s) return;

  $("#keywords").value = arrayToCsv(s.keywords);
  $("#location").value = arrayToCsv(s.location);
  setCheckedValues("experienceLevel", s.experienceLevels);
  if (s.datePosted?.[0]) $("#datePosted").value = s.datePosted[0];
  setCheckedValues("jobType", s.jobType);
  setCheckedValues("remote", s.remote);
  if (s.salary?.[0]) $("#salary").value = s.salary[0];
  if (s.sort?.[0]) $("#sort").value = s.sort[0];

  // Filters
  $("#blacklistCompanies").value = arrayToCsv(s.blacklistCompanies);
  $("#blackListTitles").value = arrayToCsv(s.blackListTitles);
  $("#onlyApplyCompanies").value = arrayToCsv(s.onlyApplyCompanies);
  $("#onlyApplyTitles").value = arrayToCsv(s.onlyApplyTitles);
  $("#blockHiringMember").value = arrayToCsv(s.blockHiringMember);
  $("#onlyApplyHiringMember").value = arrayToCsv(s.onlyApplyHiringMember);
  $("#onlyApplyMaxApplications").value = s.onlyApplyMaxApplications || "";
  $("#onlyApplyMinApplications").value = s.onlyApplyMinApplications || "";
  $("#onlyApplyJobDescription").value = arrayToCsv(s.onlyApplyJobDescription);
  $("#blockJobDescription").value = arrayToCsv(s.blockJobDescription);

  // Form fill
  $("#phoneNumber").value = s.phoneNumber || "";
  $("#preferredCv").value = s.preferredCv || 1;
  $("#defaultRadioOption").value = String(s.defaultRadioOption || 0);
  if (s.answerAllCheckboxes === true) {
    $("#answerAllCheckboxes").value = "true";
  } else if (s.answerAllCheckboxes === false) {
    $("#answerAllCheckboxes").value = "false";
  } else {
    $("#answerAllCheckboxes").value = "";
  }
  $("#additionalQuestionsText").value = keyValueToLines(s.additionalQuestions);

  // AI
  $("#useAi").checked = s.useAi || false;
  $("#openaiApiKey").value = s.openaiApiKey || "";
  if (s.openaiModel) $("#openaiModel").value = s.openaiModel;
  $("#aiResumeContext").value = s.aiResumeContext || "";

  // Advanced
  $("#dryRun").checked = s.dryRun || false;
  $("#maxApplicationsPerRun").value = s.maxApplicationsPerRun || 0;
  $("#followCompanies").checked = s.followCompanies || false;
  $("#saveBeforeApply").checked = s.saveBeforeApply || false;
  $("#outputSkippedQuestions").checked = s.outputSkippedQuestions !== false;
  $("#listNonEasyApplyJobsUrl").checked = s.listNonEasyApplyJobsUrl || false;
}

async function saveSettings() {
  const settings = gatherSettings();
  console.log("[Popup] Saving settings - keywords:", settings.keywords, "location:", settings.location);
  console.log("[Popup] Raw field values - keywords:", $("#keywords").value, "location:", $("#location").value);
  await chrome.storage.sync.set(settings);
  saveStatus.textContent = "Saved!";
  setTimeout(() => {
    saveStatus.textContent = "";
  }, 2000);
}

async function loadSettings() {
  const data = await chrome.storage.sync.get(null);
  populateSettings(data);
}

/* ───────── Bot controls ───────── */

function updateUI(status) {
  if (status.running && !status.paused) {
    statusBadge.textContent = "Running";
    statusBadge.className = "badge badge-running";
    btnStart.disabled = true;
    btnPause.disabled = false;
    btnStop.disabled = false;
  } else if (status.running && status.paused) {
    statusBadge.textContent = "Paused";
    statusBadge.className = "badge badge-paused";
    btnStart.disabled = true;
    btnPause.disabled = false;
    btnPause.textContent = "Resume";
    btnStop.disabled = false;
  } else {
    statusBadge.textContent = "Stopped";
    statusBadge.className = "badge badge-stopped";
    btnStart.disabled = false;
    btnPause.disabled = true;
    btnPause.textContent = "Pause";
    btnStop.disabled = true;
  }

  if (status.dryRun && status.running) {
    statusBadge.textContent += " (Dry Run)";
  }

  // Stats
  statJobs.textContent = status.countJobs || 0;
  statApplied.textContent = status.countApplied || 0;
  statBlacklisted.textContent = status.countBlacklisted || 0;
  statAlready.textContent = status.countAlreadyApplied || 0;
  statCannot.textContent = status.countCannotApply || 0;
  statSkipped.textContent = status.countSkipped || 0;
  statDuration.textContent = formatDuration(status.durationMs || 0);
}

btnStart.addEventListener("click", async () => {
  // Save settings first
  await saveSettings();

  // Validate required fields
  const settings = gatherSettings();
  if (!settings.keywords || settings.keywords.length === 0) {
    saveStatus.textContent = "Enter at least one keyword!";
    saveStatus.style.color = "#dc2626";
    return;
  }
  if (!settings.location || settings.location.length === 0) {
    saveStatus.textContent = "Enter at least one location!";
    saveStatus.style.color = "#dc2626";
    return;
  }
  saveStatus.style.color = "";

  // Immediately update UI to show we're trying to start
  statusBadge.textContent = "Starting...";
  statusBadge.className = "badge badge-running";
  btnStart.disabled = true;

  chrome.runtime.sendMessage({ action: "START_BOT" }, (resp) => {
    console.log("START_BOT response:", resp);
    if (chrome.runtime.lastError) {
      console.error("START_BOT error:", chrome.runtime.lastError.message);
      statusBadge.textContent = "Error";
      statusBadge.className = "badge badge-stopped";
      btnStart.disabled = false;
    }
  });

  // Start polling for status updates
  startStatusPolling();
});

btnPause.addEventListener("click", () => {
  chrome.runtime.sendMessage({ action: "PAUSE_BOT" });
});

btnStop.addEventListener("click", () => {
  chrome.runtime.sendMessage({ action: "STOP_BOT" });
});

btnSave.addEventListener("click", saveSettings);

/* ───────── Tabs ───────── */

$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    $(`#tab-${tab.dataset.tab}`).classList.add("active");
  });
});

/* ───────── Results / Export ───────── */

function renderResults(results) {
  if (!results || results.length === 0) {
    resultsLog.innerHTML = '<p class="muted">No results yet.</p>';
    return;
  }

  const typeClass = {
    APPLIED: "log-applied",
    DRY_RUN: "log-dry",
    BLACKLISTED: "log-blacklisted",
    ALREADY_APPLIED: "log-info",
    SKIPPED: "log-skip",
    CANNOT_APPLY: "log-error",
    ERROR: "log-error",
    CAP: "log-skip",
    SKIP: "log-skip",
  };

  resultsLog.innerHTML = results
    .map((r) => {
      const cls = typeClass[r.type] || "log-info";
      const time = new Date(r.timestamp).toLocaleTimeString();
      return `<div class="${cls}">[${time}] [${r.type}] ${r.message}</div>`;
    })
    .join("");

  resultsLog.scrollTop = resultsLog.scrollHeight;
}

btnExportCsv.addEventListener("click", () => {
  chrome.runtime.sendMessage({ action: "EXPORT_RESULTS" }, (resp) => {
    if (!resp?.results?.length) return;

    const header = "Timestamp,Type,Message,URL\n";
    const rows = resp.results
      .map(
        (r) =>
          `"${r.timestamp}","${r.type}","${r.message.replace(/"/g, '""')}","${r.url}"`
      )
      .join("\n");

    downloadFile(header + rows, "linkedin-bot-results.csv", "text/csv");
  });
});

btnExportJson.addEventListener("click", () => {
  chrome.runtime.sendMessage({ action: "EXPORT_RESULTS" }, (resp) => {
    if (!resp) return;
    downloadFile(
      JSON.stringify(resp, null, 2),
      "linkedin-bot-results.json",
      "application/json"
    );
  });
});

btnClearResults.addEventListener("click", () => {
  chrome.storage.local.remove(["botResults", "botStats"]);
  resultsLog.innerHTML = '<p class="muted">Results cleared.</p>';
});

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* ───────── Status updates from service worker ───────── */

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "STATUS_UPDATE") {
    updateUI(msg);
    // Also refresh results log
    chrome.storage.local.get(["botResults"], (data) => {
      if (data.botResults) renderResults(data.botResults);
    });
  }
});

/* ───────── Status polling ───────── */
let pollInterval = null;

function startStatusPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(() => {
    chrome.runtime.sendMessage({ action: "GET_STATUS" }, (status) => {
      if (chrome.runtime.lastError) return;
      if (status) {
        updateUI(status);
        // Stop polling if bot stopped
        if (!status.running) {
          clearInterval(pollInterval);
          pollInterval = null;
        }
      }
    });
    // Also refresh results
    chrome.storage.local.get(["botResults"], (data) => {
      if (data.botResults) renderResults(data.botResults);
    });
  }, 2000);
}

/* ───────── Init ───────── */

async function init() {
  await loadSettings();

  // Get current bot status
  chrome.runtime.sendMessage({ action: "GET_STATUS" }, (status) => {
    if (chrome.runtime.lastError) {
      console.log("Service worker not ready yet");
      return;
    }
    if (status) {
      updateUI(status);
      // If bot is running, start polling
      if (status.running) {
        startStatusPolling();
      }
    }
  });

  // Load saved results
  chrome.storage.local.get(["botResults"], (data) => {
    if (data.botResults) {
      renderResults(data.botResults);
    }
  });
}

init();
