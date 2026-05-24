/**
 * Service worker — orchestrates the bot.
 * Uses chrome.scripting.executeScript to run code directly in the tab.
 * No content script messaging — eliminates injection/listener issues.
 */

/* ───────── URL Generator ───────── */

const LINKEDIN_JOB_SEARCH_URL = "https://www.linkedin.com/jobs/search/";

const GEO_IDS = {
  asia: "102393603",
  europe: "100506914",
  northamerica: "102221843",
  southamerica: "104514572",
  australia: "101452733",
  africa: "103537801",
};

const EXPERIENCE_LEVEL_CODES = {
  Internship: "1", "Entry level": "2", Associate: "3",
  "Mid-Senior level": "4", Director: "5", Executive: "6",
};

const JOB_TYPE_CODES = {
  "Full-time": "F", "Part-time": "P", Contract: "C",
  Temporary: "T", Volunteer: "V", Intership: "I", Other: "O",
};

const REMOTE_CODES = { "On-site": "1", Remote: "2", Hybrid: "3" };

const SALARY_CODES = {
  "$40,000+": "1", "$60,000+": "2", "$80,000+": "3", "$100,000+": "4",
  "$120,000+": "5", "$140,000+": "6", "$160,000+": "7", "$180,000+": "8", "$200,000+": "9",
};

const SORT_CODES = { Recent: "DD", Relevent: "R" };
const DATE_POSTED_SECONDS = { "Any Time": "", "Past Month": "r2592000", "Past Week": "r604800", "Past 24 hours": "r86400" };

function buildMultiValueParam(values, codeMap, paramName) {
  if (!values || values.length === 0) return "";
  const codes = values.map((v) => codeMap[v]).filter(Boolean);
  if (codes.length === 0) return "";
  return "&" + paramName + "=" + codes.join("%2C");
}

function generateSearchUrls(settings) {
  const locations = settings.location || [];
  const keywords = settings.keywords || [];
  const urls = [];
  for (const location of locations) {
    for (const keyword of keywords) {
      let url = LINKEDIN_JOB_SEARCH_URL + "?f_AL=true";
      url += "&keywords=" + encodeURIComponent(keyword);
      url += buildMultiValueParam(settings.jobType, JOB_TYPE_CODES, "f_JT");
      url += buildMultiValueParam(settings.remote, REMOTE_CODES, "f_WT");
      url += "&location=" + encodeURIComponent(location);
      const geoId = GEO_IDS[location.toLowerCase().replace(/\s+/g, "")];
      if (geoId) url += "&geoId=" + geoId;
      url += buildMultiValueParam(settings.experienceLevels, EXPERIENCE_LEVEL_CODES, "f_E");
      const dateVal = DATE_POSTED_SECONDS[(settings.datePosted || [])[0]] || "";
      if (dateVal) url += "&f_TPR=" + dateVal;
      const salaryCode = SALARY_CODES[(settings.salary || [])[0]] || "";
      if (salaryCode) url += "&f_SB2=" + salaryCode;
      const sortCode = SORT_CODES[(settings.sort || [])[0]] || "";
      if (sortCode) url += "&sortBy=" + sortCode;
      urls.push(url);
    }
  }
  return urls;
}

/* ───────── State ───────── */
let botState = {
  running: false, paused: false, dryRun: false,
  urls: [], currentUrlIndex: 0,
  countJobs: 0, countApplied: 0, countBlacklisted: 0,
  countAlreadyApplied: 0, countCannotApply: 0, countSkipped: 0,
  maxApplicationsPerRun: 0, startTime: 0, tabId: null, results: [],
};

const JOBS_PER_PAGE = 25;

function randomDelayMs(min = 2000, max = 5000) {
  return Math.floor(Math.random() * (max - min) + min);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/* ───────── Settings ───────── */
async function loadSettings() {
  return new Promise((resolve) => chrome.storage.sync.get(null, resolve));
}

async function saveResults() {
  await chrome.storage.local.set({
    botResults: botState.results,
    botStats: {
      countJobs: botState.countJobs, countApplied: botState.countApplied,
      countBlacklisted: botState.countBlacklisted,
      countAlreadyApplied: botState.countAlreadyApplied,
      countCannotApply: botState.countCannotApply,
      countSkipped: botState.countSkipped,
      startTime: botState.startTime, endTime: Date.now(),
    },
  });
}

/* ───────── Tab navigation ───────── */
function navigateTab(url) {
  console.log("[Bot] Navigating:", url.substring(0, 120));
  return new Promise((resolve) => {
    let resolved = false;
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        chrome.tabs.onUpdated.removeListener(listener);
        console.warn("[Bot] Navigation timeout");
        resolve();
      }
    }, 30000);

    function listener(tabId, changeInfo) {
      if (tabId === botState.tabId && changeInfo.status === "complete" && !resolved) {
        resolved = true;
        clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(listener);
        const delay = randomDelayMs();
        console.log("[Bot] Page loaded, waiting", delay, "ms");
        setTimeout(resolve, delay);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.update(botState.tabId, { url });
  });
}

/**
 * Execute a function in the LinkedIn tab and return its result.
 * This runs directly via chrome.scripting — no content script messaging needed.
 */
async function runInTab(func, args = []) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: botState.tabId },
      func: func,
      args: args,
    });
    return results[0]?.result;
  } catch (e) {
    console.error("[Bot] runInTab error:", e.message);
    return null;
  }
}

/* ───────── Functions that run INSIDE the LinkedIn tab ───────── */
// These are serialized and sent to the tab. They cannot reference outer scope.

function TAB_getTotalJobs() {
  const el = document.querySelector("small");
  if (!el) return 0;
  const match = el.textContent.replace(/,/g, "").match(/(\d+)/);
  return match ? parseInt(match[1], 10) : 0;
}

function TAB_getJobIds() {
  const cards = document.querySelectorAll("li[data-occludable-job-id]");
  const ids = [];
  for (const card of cards) {
    const rawId = card.getAttribute("data-occludable-job-id");
    if (!rawId) continue;
    const jobId = rawId.split(":").pop();
    // Skip already applied
    if (card.textContent.includes("Applied")) continue;
    ids.push(jobId);
  }
  return ids;
}

function TAB_diagnosePage() {
  // CRITICAL: Find every element containing "Easy Apply" text and trace its DOM path
  const easyApplyElements = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.includes("Easy Apply")) {
      let el = walker.currentNode.parentElement;
      const chain = [];
      for (let i = 0; i < 5 && el; i++) {
        chain.push({
          tag: el.tagName.toLowerCase(),
          classes: el.className?.toString().substring(0, 100) || "",
          id: el.id || "",
          role: el.getAttribute("role") || "",
          ariaLabel: el.getAttribute("aria-label") || "",
          visible: el.offsetParent !== null,
        });
        el = el.parentElement;
      }
      easyApplyElements.push(chain);
    }
  }

  // Also find ALL clickable elements near "Easy Apply" text
  const allClickable = [...document.querySelectorAll("button, a, [role='button'], [tabindex='0']")]
    .filter(el => el.textContent.includes("Apply") && el.offsetParent !== null)
    .map(el => ({
      tag: el.tagName.toLowerCase(),
      text: el.textContent.trim().substring(0, 60),
      classes: el.className?.toString().substring(0, 100) || "",
      ariaLabel: el.getAttribute("aria-label") || "",
      href: el.getAttribute("href")?.substring(0, 60) || "",
    }));

  return {
    url: window.location.href,
    bodyLength: document.body.innerHTML.length,
    hasEasyApply: document.body.textContent.includes("Easy Apply"),
    easyApplyDomPaths: easyApplyElements.slice(0, 5),
    clickableApplyElements: allClickable.slice(0, 10),
    totalButtons: document.querySelectorAll("button").length,
  };
}

// ── STEP 1: Analyze page, check filters, click Easy Apply ──
// Returns: { status, message, label } — if status is "clicked", the Easy Apply was clicked
function TAB_clickEasyApply(settings) {
  function sleepMs(ms) { return new Promise((r) => setTimeout(r, ms)); }

  async function waitForContent(timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const btns = document.querySelectorAll("button, a, [role='button']");
      for (const b of btns) {
        if (b.textContent.toLowerCase().includes("easy apply") && b.offsetParent !== null) return true;
      }
      if (document.body.textContent.includes("Easy Apply")) return true;
      const jd = document.querySelector("[class*='job-details'], [class*='jobs-unified-top-card']");
      if (jd && jd.textContent.trim().length > 50) return true;
      await sleepMs(800);
    }
    return false;
  }

  function getProps() {
    let title = "", company = "", location = "";

    // Title: use specific job-title selectors FIRST, h1 as last resort
    const titleSels = [
      "[class*='job-title']",
      "[class*='top-card'] h1",
      "[class*='topcard'] h1",
      "h1[class*='title']",
      ".jobs-unified-top-card h1",
    ];
    for (const sel of titleSels) {
      try { const el = document.querySelector(sel); if (el?.textContent.trim().length > 3) { title = el.textContent.trim(); break; } } catch {}
    }
    // Fallback: use <title> tag which usually has "Job Title | Company | LinkedIn"
    if (!title) {
      try {
        const pageTitle = document.title || "";
        if (pageTitle.includes("|")) {
          title = pageTitle.split("|")[0].trim();
          // Remove "hiring" prefix if present
          title = title.replace(/^.*hiring\s*/i, "").trim();
        }
      } catch {}
    }
    // Last fallback: first h1 that's NOT in the nav
    if (!title) {
      try {
        const h1s = document.querySelectorAll("h1");
        for (const h of h1s) {
          const txt = h.textContent.trim();
          // Skip nav-related h1s
          if (txt.includes("notification") || txt.length < 4 || txt.length > 200) continue;
          const inNav = h.closest("nav, header, [class*='global-nav']");
          if (!inNav) { title = txt; break; }
        }
      } catch {}
    }

    for (const sel of ["a[href*='/company/']", "[class*='company-name'] a"]) {
      try { const el = document.querySelector(sel); if (el?.textContent.trim().length > 0) { company = el.textContent.trim(); break; } } catch {}
    }
    for (const sel of ["[class*='bullet']", "[class*='location']"]) {
      try { const el = document.querySelector(sel); if (el?.textContent.trim().length > 2) { location = el.textContent.trim(); break; } } catch {}
    }
    let description = "";
    for (const sel of [".jobs-description__content", "#job-details", "[class*='description']"]) {
      try { const el = document.querySelector(sel); if (el?.textContent.trim().length > 20) { description = el.textContent.trim(); break; } } catch {}
    }
    return { title, company, location, description };
  }

  function checkBlacklist(props, s) {
    const t = (props.title || "").toLowerCase(), co = (props.company || "").toLowerCase(), d = (props.description || "").toLowerCase();
    const bl = (s.blacklistCompanies || []).map(c => c.toLowerCase());
    if (bl.some(bc => co.includes(bc))) return "Blacklisted company";
    const bt = (s.blackListTitles || []).map(x => x.toLowerCase());
    if (bt.some(x => t.includes(x))) return "Blacklisted title";
    const oc = (s.onlyApplyCompanies || []).map(c => c.toLowerCase());
    if (oc.length > 0 && !oc.some(c => co.includes(c))) return "Not in company whitelist";
    const ot = (s.onlyApplyTitles || []).map(x => x.toLowerCase());
    if (ot.length > 0 && !ot.some(x => t.includes(x))) return "Not in title whitelist";
    const bd = (s.blockJobDescription || []).map(k => k.toLowerCase());
    if (bd.some(k => d.includes(k))) return "Blocked description keyword";
    const od = (s.onlyApplyJobDescription || []).map(k => k.toLowerCase());
    if (od.length > 0 && !od.some(k => d.includes(k))) return "Missing required description keyword";
    return null;
  }

  function findEasyApply() {
    // <a> with aria-label (current LinkedIn)
    let el = document.querySelector("a[aria-label*='Easy Apply']");
    if (el?.offsetParent !== null) return el;
    el = document.querySelector("button[aria-label*='Easy Apply']");
    if (el?.offsetParent !== null) return el;
    el = document.querySelector("[aria-label*='Easy Apply']");
    if (el?.offsetParent !== null) return el;
    // Scan all clickable
    for (const c of document.querySelectorAll("button, a, [role='button']")) {
      if (c.textContent.trim().toLowerCase().includes("easy apply") && c.offsetParent !== null) return c;
    }
    return null;
  }

  return (async () => {
    await waitForContent(20000);
    await sleepMs(2000);
    const props = getProps();
    const label = [props.title || "(no title)", props.company || "(no company)"].filter(Boolean).join(" @ ");
    const blReason = checkBlacklist(props, settings);
    if (blReason) return { status: "blacklisted", message: label + " - " + blReason, label };
    const easyBtn = findEasyApply();
    if (!easyBtn) {
      if (document.body.textContent.includes("Applied")) return { status: "already_applied", message: label + " - Already applied", label };
      return { status: "cannot_apply", message: label + " - No Easy Apply button found", label };
    }
    // Return the href so the service worker can navigate to the apply page
    const applyUrl = easyBtn.href || easyBtn.getAttribute("href") || "";
    return { status: "clicked", message: label + " - Easy Apply found", label, applyUrl };
  })();
}

// ── STEP 2: Handle one form step (fill fields, find next action) ──
// Returns: { action: "submit"|"continue"|"review"|"stuck"|"waiting", formElements: [...] }
function TAB_handleFormStep(settings) {
  function sleepMs(ms) { return new Promise((r) => setTimeout(r, ms)); }

  // Wait for the Easy Apply modal/dialog to appear
  async function waitForModal(timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      // Check for dialog/modal containers
      const modal = document.querySelector(
        "[role='dialog'], [class*='artdeco-modal'], [class*='jobs-easy-apply-modal'], " +
        "[class*='jobs-apply-form'], [class*='easy-apply'], [class*='jpac-modal']"
      );
      if (modal && modal.textContent.trim().length > 20) return modal;

      // Check for any form inside an overlay
      const overlay = document.querySelector("[class*='overlay'] form, [class*='modal'] form");
      if (overlay) return overlay;

      // Check for Submit/Continue/Review buttons anywhere (they only appear in the form)
      for (const el of document.querySelectorAll("button, [role='button']")) {
        const aria = (el.getAttribute("aria-label") || "").toLowerCase();
        const txt = el.textContent.trim().toLowerCase();
        if (aria.includes("submit application") || aria.includes("continue to next") ||
            aria.includes("review your application") || txt.includes("submit application") ||
            txt.includes("next") || aria.includes("dismiss")) {
          return el.closest("[role='dialog'], [class*='modal'], [class*='overlay']") || document.body;
        }
      }

      await sleepMs(800);
    }
    return null;
  }
  function fillPhone(phoneNumber) {
    if (!phoneNumber) return;
    for (const sel of ["input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]"]) {
      for (const inp of document.querySelectorAll(sel)) {
        if (inp.offsetParent !== null && inp.value === "") {
          inp.focus(); inp.value = phoneNumber;
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
          return;
        }
      }
    }
  }

  function fillInputFields(answers) {
    if (!answers || Object.keys(answers).length === 0) return;
    for (const group of document.querySelectorAll(".jobs-easy-apply-form-section__grouping, [class*='form-component'], .fb-dash-form-element")) {
      const lbl = group.querySelector("label, legend, span[class*='label']");
      if (!lbl) continue;
      const labelText = lbl.textContent.trim().toLowerCase();
      const input = group.querySelector("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])");
      if (!input || input.value !== "" || input.offsetParent === null) continue;
      for (const [key, value] of Object.entries(answers)) {
        if (labelText.includes(key.toLowerCase())) {
          input.focus(); input.value = String(value);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
          break;
        }
      }
    }
  }

  function fillRadios(defaultOption) {
    if (!defaultOption) return;
    for (const fs of document.querySelectorAll("fieldset")) {
      const radios = fs.querySelectorAll("input[type='radio']");
      if (radios.length === 0 || [...radios].some(r => r.checked)) continue;
      const idx = Math.min(defaultOption - 1, radios.length - 1);
      if (radios[idx]) radios[idx].click();
    }
  }

  function chooseResume(preferredCv) {
    try {
      const req = document.querySelector(".jobs-document-upload__title--is-required");
      if (!req) return;
      const resumes = document.querySelectorAll("div[class*='ui-attachment--pdf']");
      if (resumes.length === 0) return;
      const idx = Math.min((preferredCv || 1) - 1, resumes.length - 1);
      if (resumes[idx]?.getAttribute("aria-label") === "Select this resume") resumes[idx].click();
    } catch {}
  }

  function findClickable(ariaLabels, textMatches) {
    for (const al of ariaLabels) {
      const el = document.querySelector("[aria-label='" + al + "'], [aria-label*='" + al + "']");
      if (el?.offsetParent !== null) return el;
    }
    for (const c of document.querySelectorAll("button, a, [role='button'], footer button, footer a")) {
      const txt = c.textContent.trim().toLowerCase();
      for (const tm of textMatches) {
        if (txt.includes(tm.toLowerCase()) && c.offsetParent !== null) return c;
      }
    }
    return null;
  }

  // Main async flow — wait for modal, then fill and act
  return (async () => {
    // Wait for the Easy Apply modal to appear
    const modal = await waitForModal(15000);
    if (!modal) {
      // No modal found — dump what's on the page
      const visible = [...document.querySelectorAll("button, a, [role='button'], [role='dialog'], [class*='modal']")]
        .filter(el => el.offsetParent !== null)
        .map(el => el.tagName + "[" + (el.getAttribute("aria-label") || el.getAttribute("role") || el.textContent.trim().substring(0, 40)) + "]")
        .filter(t => t.length > 3);
      return { action: "stuck", formElements: visible.slice(0, 15), debug: "no modal found" };
    }

    // Fill all fields
    chooseResume(settings.preferredCv || 1);
    fillPhone(settings.phoneNumber || "");
    fillInputFields(settings.additionalQuestions || {});
    fillRadios(settings.defaultRadioOption || 0);

    // Unfollow if needed
    if (!settings.followCompanies) {
      try { const l = document.querySelector("label[for='follow-company-checkbox']"); if (l) l.click(); } catch {}
    }

    // Find next action
    const submitEl = findClickable(["Submit application", "Submit"], ["submit application"]);
    if (submitEl) { submitEl.click(); return { action: "submit" }; }

    const reviewEl = findClickable(["Review your application", "Review"], ["review your application"]);
    if (reviewEl) { reviewEl.click(); return { action: "review" }; }

    const continueEl = findClickable(["Continue to next step", "Next"], ["continue to next step", "next"]);
    if (continueEl) { continueEl.click(); return { action: "continue" }; }

    // Stuck — dump visible elements INSIDE the modal
    const modalEls = [...(modal.querySelectorAll ? modal.querySelectorAll("button, a, [role='button'], input, select") : [])]
      .filter(el => el.offsetParent !== null)
      .map(el => el.tagName + "[" + (el.getAttribute("aria-label") || el.getAttribute("type") || el.textContent.trim().substring(0, 40)) + "]")
      .filter(t => t.length > 3);

    // Also check all dialogs on page
    const allDialogs = [...document.querySelectorAll("[role='dialog'], [class*='modal'], [class*='overlay']")]
      .map(d => ({ classes: d.className?.toString().substring(0, 80), children: d.children.length, text: d.textContent.trim().substring(0, 100) }));

    return { action: "stuck", formElements: modalEls.slice(0, 15), dialogs: allDialogs.slice(0, 3), debug: "modal found but no nav buttons" };
  })();
}

/* ───────── Claude AI Integration ───────── */

/**
 * Call Claude API to answer a form question.
 * Runs in the service worker (has fetch access).
 */
async function askOpenAI(apiKey, model, resumeContext, question, fieldType, options) {
  const systemPrompt = `You are filling out a job application form on LinkedIn. Answer the question based on the applicant's profile below. Rules:
- Be concise and direct
- For text fields: give ONLY the answer, no explanation
- For radio/select fields: respond with EXACTLY one of the provided options
- For numeric fields: respond with ONLY a number
- If the question asks about years of experience with a specific skill, give a number
- If you don't know, make a reasonable professional answer
- Never say "I" - answer as if you are the applicant
- For disability: No
- For veteran: No
- For gender: Male
- For race/ethnicity: Black or African American
- For Hispanic/Latino: No
- For sexual orientation: Heterosexual
- For sponsorship: No
- For work authorization: Yes
- NEVER choose "Decline" or "Prefer not to say" - always give a real answer
- Keep dropdown answers SHORT (1-3 words)

Applicant profile:
${resumeContext}`;

  const userMsg = `Question: "${question}"
Field type: ${fieldType}${options && options.length > 0 ? "\nOptions: " + options.join(", ") : ""}
Answer:`;

  try {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 150,
        system: systemPrompt,
        messages: [
          { role: "user", content: userMsg },
        ],
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      console.error("[Bot] Claude error:", resp.status, err.substring(0, 200));
      return null;
    }

    const data = await resp.json();
    const answer = data.content?.[0]?.text?.trim();
    console.log("[Bot] AI answer for '" + question.substring(0, 50) + "':", answer);
    return answer;
  } catch (e) {
    console.error("[Bot] Claude fetch error:", e.message);
    return null;
  }
}

/**
 * Extract unfilled required fields from the form page.
 * Runs inside the LinkedIn tab.
 */
function TAB_getUnfilledFields() {
  const fields = [];

  // Text/number inputs
  const groups = document.querySelectorAll(
    ".jobs-easy-apply-form-section__grouping, [class*='form-component'], .fb-dash-form-element, [class*='form-section']"
  );
  for (const group of groups) {
    const lbl = group.querySelector("label, legend, span[class*='label'], [class*='question']");
    if (!lbl) continue;
    const question = lbl.textContent.trim();
    if (!question || question.length < 3) continue;

    // Text/number input
    const input = group.querySelector("input:not([type='hidden']):not([type='checkbox']):not([type='radio']), textarea");
    if (input && input.offsetParent !== null && input.value.trim() === "") {
      fields.push({ question, type: input.type || "text", selector: getSelector(input), options: [] });
      continue;
    }

    // Select/dropdown
    const select = group.querySelector("select");
    if (select && select.offsetParent !== null && (!select.value || select.selectedIndex <= 0)) {
      const opts = [...select.options].filter(o => o.value).map(o => o.text.trim());
      fields.push({ question, type: "select", selector: getSelector(select), options: opts });
      continue;
    }

    // Radio buttons
    const radios = group.querySelectorAll("input[type='radio']");
    if (radios.length > 0 && ![...radios].some(r => r.checked)) {
      const labels = [...group.querySelectorAll("label")].map(l => l.textContent.trim()).filter(t => t.length > 0 && t !== question);
      fields.push({ question, type: "radio", selector: "", options: labels });
      continue;
    }
  }

  function getSelector(el) {
    if (el.id) return "#" + el.id;
    if (el.name) return "[name='" + el.name + "']";
    return "";
  }

  return fields;
}

/**
 * Fill a specific field with an AI-generated answer.
 * Runs inside the LinkedIn tab.
 */
function TAB_fillAiAnswer(question, answer, fieldType, selector) {
  function setInputValue(el, val) {
    el.focus();
    el.value = val;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // Try by selector first
  if (selector) {
    const el = document.querySelector(selector);
    if (el && el.offsetParent !== null) {
      if (fieldType === "select") {
        const opt = [...el.options].find(o => o.text.toLowerCase().includes(answer.toLowerCase()));
        if (opt) { el.value = opt.value; el.dispatchEvent(new Event("change", { bubbles: true })); return true; }
      } else {
        setInputValue(el, answer);
        return true;
      }
    }
  }

  // Fallback: find by question text
  const groups = document.querySelectorAll(
    ".jobs-easy-apply-form-section__grouping, [class*='form-component'], .fb-dash-form-element, [class*='form-section']"
  );
  for (const group of groups) {
    const lbl = group.querySelector("label, legend, span[class*='label'], [class*='question']");
    if (!lbl || !lbl.textContent.trim().toLowerCase().includes(question.toLowerCase().substring(0, 30))) continue;

    if (fieldType === "radio") {
      const labels = group.querySelectorAll("label");
      for (const lab of labels) {
        if (lab.textContent.trim().toLowerCase().includes(answer.toLowerCase())) {
          const radio = lab.querySelector("input[type='radio']") || lab.previousElementSibling;
          if (radio) { radio.click(); return true; }
        }
      }
      // Fallback: click first radio if answer doesn't match options
      const firstRadio = group.querySelector("input[type='radio']");
      if (firstRadio) { firstRadio.click(); return true; }
    }

    if (fieldType === "select") {
      const select = group.querySelector("select");
      if (select) {
        const opt = [...select.options].find(o => o.text.toLowerCase().includes(answer.toLowerCase()));
        if (opt) { select.value = opt.value; select.dispatchEvent(new Event("change", { bubbles: true })); return true; }
      }
    }

    const input = group.querySelector("input:not([type='hidden']):not([type='checkbox']):not([type='radio']), textarea");
    if (input && input.offsetParent !== null) {
      setInputValue(input, answer);
      return true;
    }
  }
  return false;
}

/* ───────── Core bot loop ───────── */
async function startBot() {
  console.log("[Bot] Starting...");
  const settings = await loadSettings();
  console.log("[Bot] Settings:", JSON.stringify({ keywords: settings.keywords, location: settings.location, dryRun: settings.dryRun }));

  botState.running = true;
  botState.paused = false;
  botState.dryRun = settings.dryRun || false;
  botState.maxApplicationsPerRun = settings.maxApplicationsPerRun || 0;
  botState.startTime = Date.now();
  botState.countJobs = 0;
  botState.countApplied = 0;
  botState.countBlacklisted = 0;
  botState.countAlreadyApplied = 0;
  botState.countCannotApply = 0;
  botState.countSkipped = 0;
  botState.results = [];

  botState.urls = generateSearchUrls(settings);
  console.log("[Bot] Generated", botState.urls.length, "URLs");

  if (botState.urls.length === 0) {
    logResult("ERROR", "No URLs generated. Need keywords + locations.");
    botState.running = false;
    await saveResults();
    broadcastStatus();
    return;
  }

  // Find LinkedIn tab
  const tabs = await chrome.tabs.query({ url: "https://www.linkedin.com/*" });
  if (tabs.length > 0) {
    botState.tabId = tabs[0].id;
    console.log("[Bot] Using tab:", botState.tabId);
  } else {
    const newTab = await chrome.tabs.create({ url: "https://www.linkedin.com/jobs/" });
    botState.tabId = newTab.id;
    await sleep(5000);
  }

  broadcastStatus();

  try {
    await processUrls(settings);
  } catch (e) {
    console.error("[Bot] Fatal:", e);
    logResult("ERROR", "Fatal: " + e.message);
  }

  botState.running = false;
  await saveResults();
  broadcastStatus();
}

async function processUrls(settings) {
  for (let i = 0; i < botState.urls.length; i++) {
    if (!botState.running) break;
    while (botState.paused) await sleep(1000);

    const searchUrl = botState.urls[i];
    await navigateTab(searchUrl);

    // Get total jobs — run directly in tab
    const totalJobs = await runInTab(TAB_getTotalJobs);
    console.log("[Bot] Total jobs:", totalJobs);

    if (!totalJobs || totalJobs === 0) {
      logResult("SKIP", "No jobs found for: " + searchUrl.substring(0, 80));
      continue;
    }

    const totalPages = Math.min(Math.ceil(totalJobs / JOBS_PER_PAGE), 40);

    for (let page = 0; page < totalPages; page++) {
      if (!botState.running) break;
      while (botState.paused) await sleep(1000);

      const pageUrl = searchUrl + "&start=" + (page * JOBS_PER_PAGE);
      if (page > 0) await navigateTab(pageUrl);

      // Get job IDs — run directly in tab
      const jobIds = await runInTab(TAB_getJobIds);
      console.log("[Bot] Page", page, "- found", jobIds?.length || 0, "jobs");

      if (!jobIds || jobIds.length === 0) continue;

      for (const jobId of jobIds) {
        if (!botState.running) break;
        while (botState.paused) await sleep(1000);

        // Check cap
        if (botState.maxApplicationsPerRun > 0 && botState.countApplied >= botState.maxApplicationsPerRun) {
          logResult("CAP", "Reached limit: " + botState.maxApplicationsPerRun);
          botState.running = false;
          break;
        }

        const jobUrl = "https://www.linkedin.com/jobs/view/" + jobId;
        await navigateTab(jobUrl);
        botState.countJobs++;

        // STEP 1: Analyze page + click Easy Apply
        const step1 = await runInTab(TAB_clickEasyApply, [settings]);
        console.log("[Bot] Step1:", step1?.status, "-", step1?.message?.substring(0, 100));

        if (!step1 || step1.status !== "clicked") {
          // Not clicked — handle the status
          if (!step1) { botState.countCannotApply++; logResult("ERROR", "No response from tab", jobUrl); }
          else if (step1.status === "blacklisted") { botState.countBlacklisted++; logResult("BLACKLISTED", step1.message, jobUrl); }
          else if (step1.status === "already_applied") { botState.countAlreadyApplied++; logResult("ALREADY_APPLIED", step1.message, jobUrl); }
          else { botState.countCannotApply++; logResult("CANNOT_APPLY", step1.message, jobUrl); }
        } else {
          // Easy Apply found — navigate to the apply URL directly
          const label = step1.label || "";
          const applyUrl = step1.applyUrl || "";
          console.log("[Bot] Apply URL:", applyUrl?.substring(0, 120));

          if (applyUrl && applyUrl.startsWith("http")) {
            // Navigate to the apply page
            await navigateTab(applyUrl);
          } else {
            // No URL — try clicking in the tab as fallback
            await runInTab(() => {
              const btn = document.querySelector("a[aria-label*='Easy Apply'], [aria-label*='Easy Apply']");
              if (btn) btn.click();
            });
            await sleep(randomDelayMs(3000, 5000));
          }

          let applied = false;
          let stuck = false;
          for (let formStep = 0; formStep < 12; formStep++) {
            // Run form step in the current tab (may be a new page after click)
            const stepResult = await runInTab(TAB_handleFormStep, [settings]);
            console.log("[Bot] FormStep", formStep, ":", stepResult?.action, stepResult?.formElements?.slice(0, 5)?.join(", ") || "");

            if (!stepResult || stepResult.action === "stuck") {
              // Try AI to answer unfilled fields
              if (settings.useAi && settings.openaiApiKey) {
                console.log("[Bot] Form stuck — trying AI...");
                const unfilled = await runInTab(TAB_getUnfilledFields);
                console.log("[Bot] Unfilled fields:", JSON.stringify(unfilled?.slice(0, 5)));

                if (unfilled && unfilled.length > 0) {
                  let aiFilled = 0;
                  for (const field of unfilled) {
                    const answer = await askOpenAI(
                      settings.openaiApiKey,
                      settings.openaiModel,
                      settings.aiResumeContext || "",
                      field.question,
                      field.type,
                      field.options
                    );
                    if (answer) {
                      const filled = await runInTab(TAB_fillAiAnswer, [field.question, answer, field.type, field.selector]);
                      if (filled) aiFilled++;
                    }
                  }
                  console.log("[Bot] AI filled", aiFilled, "/", unfilled.length, "fields");
                  if (aiFilled > 0) {
                    // Retry the form step after AI filled fields
                    await sleep(500);
                    const retryResult = await runInTab(TAB_handleFormStep, [settings]);
                    console.log("[Bot] Retry after AI:", retryResult?.action);
                    if (retryResult && retryResult.action !== "stuck") {
                      if (retryResult.action === "submit") {
                        if (botState.dryRun) { logResult("DRY_RUN", label + " - DRY RUN (AI helped, would submit)", jobUrl); }
                        else { botState.countApplied++; logResult("APPLIED", label + " - Applied (AI helped)!", jobUrl); }
                        applied = true;
                      }
                      // continue/review — let the loop continue
                      if (!applied) { await sleep(randomDelayMs(2000, 3500)); continue; }
                      break;
                    }
                  }
                }
              }

              // Still stuck after AI attempt (or AI not enabled)
              const elements = stepResult?.formElements?.join(" | ") || "none";
              const debug = stepResult?.debug || "";
              console.log("[Bot] STUCK.", debug, "Elements:", elements);
              if (botState.dryRun) {
                logResult("DRY_RUN", label + " - DRY RUN (form reached step " + (formStep + 1) + ")", jobUrl);
              } else {
                botState.countCannotApply++;
                logResult("CANNOT_APPLY", label + " - Form stuck at step " + (formStep + 1) + ". Elements: [" + elements + "]", jobUrl);
              }
              stuck = true;
              break;
            }

            if (stepResult.action === "submit") {
              if (botState.dryRun) {
                logResult("DRY_RUN", label + " - DRY RUN (would submit)", jobUrl);
              } else {
                botState.countApplied++;
                logResult("APPLIED", label + " - Applied!", jobUrl);
              }
              applied = true;
              break;
            }

            // "continue" or "review" — wait for next step to load
            await sleep(randomDelayMs(2000, 3500));
          }

          if (!applied && !stuck) {
            botState.countCannotApply++;
            logResult("CANNOT_APPLY", label + " - Too many form steps", jobUrl);
          }
        }

        broadcastStatus();
        await saveResults();
      }
    }
  }
}

function stopBot() { botState.running = false; broadcastStatus(); }
function pauseBot() { botState.paused = !botState.paused; broadcastStatus(); }

/* ───────── Logging ───────── */
function logResult(type, message, url = "") {
  botState.results.push({ timestamp: new Date().toISOString(), type, message, url });
}

/* ───────── Message handling ───────── */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.action) {
    case "START_BOT":
      startBot().catch((e) => console.error("[Bot] startBot error:", e));
      sendResponse({ ok: true });
      break;
    case "STOP_BOT": stopBot(); sendResponse({ ok: true }); break;
    case "PAUSE_BOT": pauseBot(); sendResponse({ ok: true, paused: botState.paused }); break;
    case "GET_STATUS": sendResponse(getStatus()); break;
    case "EXPORT_RESULTS":
      sendResponse({
        results: botState.results,
        stats: {
          countJobs: botState.countJobs, countApplied: botState.countApplied,
          countBlacklisted: botState.countBlacklisted, countAlreadyApplied: botState.countAlreadyApplied,
          countCannotApply: botState.countCannotApply, countSkipped: botState.countSkipped,
          durationMs: botState.startTime ? Date.now() - botState.startTime : 0,
        },
      });
      break;
    default: sendResponse({ error: "Unknown action" });
  }
  return true;
});

function getStatus() {
  return {
    running: botState.running, paused: botState.paused, dryRun: botState.dryRun,
    countJobs: botState.countJobs, countApplied: botState.countApplied,
    countBlacklisted: botState.countBlacklisted, countAlreadyApplied: botState.countAlreadyApplied,
    countCannotApply: botState.countCannotApply, countSkipped: botState.countSkipped,
    currentUrlIndex: botState.currentUrlIndex, totalUrls: botState.urls.length,
    durationMs: botState.startTime ? Date.now() - botState.startTime : 0,
  };
}

function broadcastStatus() {
  chrome.runtime.sendMessage({ action: "STATUS_UPDATE", ...getStatus() }).catch(() => {});
}
