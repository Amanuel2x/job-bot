/**
 * Content script — Easy Apply automation.
 * Handles clicking Easy Apply, multi-step forms, phone filling,
 * resume selection, additional questions, and form submission.
 */

// Remove old listener if re-injected, to avoid duplicate handlers
if (window.__jobApplierListener) {
  chrome.runtime.onMessage.removeListener(window.__jobApplierListener);
}

{  // Block scope to avoid redeclaration errors on re-injection

/* ───────── DOM helpers (shared with jobScanner.js) ───────── */

if (typeof waitForElement === "undefined") {
  // Re-declare only if jobScanner.js hasn't loaded first
  function waitForElement(selector, timeoutMs = 10000, parent = document) {
    return new Promise((resolve) => {
      const existing = parent.querySelector(selector);
      if (existing) return resolve(existing);
      const observer = new MutationObserver(() => {
        const el = parent.querySelector(selector);
        if (el) {
          observer.disconnect();
          resolve(el);
        }
      });
      observer.observe(parent, { childList: true, subtree: true });
      setTimeout(() => {
        observer.disconnect();
        resolve(null);
      }, timeoutMs);
    });
  }
}

if (typeof sleep === "undefined") {
  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }
}

if (typeof randomDelay === "undefined") {
  function randomDelay(min = 2000, max = 5000) {
    return sleep(Math.floor(Math.random() * (max - min) + min));
  }
}

/* ───────── Page load detection ───────── */

/**
 * Wait for the LinkedIn job page to actually render its content.
 * LinkedIn is a React SPA — the DOM loads first, then React hydrates.
 * We need to wait for actual job content to appear.
 * @param {number} timeoutMs
 * @returns {Promise<boolean>} true if content found
 */
async function waitForPageContent(timeoutMs = 15000) {
  const startTime = Date.now();
  const selectors = [
    // Job title selectors (various LinkedIn versions)
    "h1",
    "h2.job-details-jobs-unified-top-card__job-title",
    "[class*='job-title']",
    "[class*='top-card'] h1",
    "[class*='top-card'] h2",
    // Apply button area
    "[class*='jobs-apply-button']",
    "[class*='apply-button']",
    // Job details container
    "[class*='job-details']",
    "[class*='jobs-unified-top-card']",
    ".jobs-search__job-details",
  ];

  while (Date.now() - startTime < timeoutMs) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 0) {
        console.log("[EasyApply] Page content detected via:", sel);
        return true;
      }
    }
    // Also check for any button containing "Apply" or "Easy Apply"
    const buttons = document.querySelectorAll("button");
    for (const btn of buttons) {
      const text = btn.textContent.toLowerCase();
      if (text.includes("apply") || text.includes("save")) {
        console.log("[EasyApply] Page content detected via button:", btn.textContent.trim().substring(0, 40));
        return true;
      }
    }
    await sleep(500);
  }
  return false;
}

/* ───────── Easy Apply button ───────── */

/**
 * Find and return the Easy Apply button, or null if not found.
 * Uses multiple strategies to handle LinkedIn DOM variations.
 */
function findEasyApplyButton() {
  // Strategy 1: Primary class-based selectors
  const primarySelectors = [
    "div[class*='jobs-apply-button--top-card'] button[class*='jobs-apply-button']",
    "button[class*='jobs-apply-button']",
    "[class*='jobs-apply'] button",
    "[class*='apply-button'] button",
    "button[aria-label*='Easy Apply']",
    "button[aria-label*='easy apply']",
  ];

  for (const sel of primarySelectors) {
    try {
      const btn = document.querySelector(sel);
      if (btn && btn.textContent.toLowerCase().includes("easy apply")) {
        console.log("[EasyApply] Button found via selector:", sel);
        return btn;
      }
    } catch { /* ignore invalid selectors */ }
  }

  // Strategy 2: Find by text content — most resilient
  const allButtons = document.querySelectorAll("button");
  for (const b of allButtons) {
    const text = b.textContent.toLowerCase().trim();
    if (text.includes("easy apply") && !b.disabled && b.offsetParent !== null) {
      console.log("[EasyApply] Button found via text match:", b.textContent.trim().substring(0, 40));
      return b;
    }
  }

  // Strategy 3: Check for LinkedIn's SVG icon + "Easy Apply" in parent
  const spans = document.querySelectorAll("span");
  for (const span of spans) {
    if (span.textContent.trim().toLowerCase() === "easy apply") {
      const btn = span.closest("button");
      if (btn && !btn.disabled) {
        console.log("[EasyApply] Button found via span text in parent button");
        return btn;
      }
    }
  }

  console.log("[EasyApply] No Easy Apply button found on page");
  return null;
}

/* ───────── Resume selection ───────── */

/**
 * Select the preferred resume if a resume picker is shown.
 * @param {number} preferredCv - 1-based index of preferred CV
 */
async function chooseResume(preferredCv = 1) {
  try {
    const requiredLabel = document.querySelector(
      ".jobs-document-upload__title--is-required"
    );
    if (!requiredLabel) return;

    const resumes = document.querySelectorAll(
      "div[class*='ui-attachment--pdf']"
    );
    if (resumes.length === 0) return;

    const index = Math.min(preferredCv - 1, resumes.length - 1);
    const targetResume = resumes[index];

    if (
      targetResume &&
      targetResume.getAttribute("aria-label") === "Select this resume"
    ) {
      targetResume.click();
      await sleep(500);
    }
  } catch {
    // Resume selection is best-effort
  }
}

/* ───────── Phone number filling ───────── */

/**
 * Fill phone number fields if they exist and are empty.
 * @param {string} phoneNumber - Phone number to fill
 */
async function fillPhoneNumber(phoneNumber) {
  if (!phoneNumber) return false;

  const cssSelectors = [
    "input[type='tel']",
    "input[name*='phone' i]",
    "input[id*='phone' i]",
    "input[aria-label*='phone' i]",
    "input[placeholder*='phone' i]",
  ];

  for (const selector of cssSelectors) {
    try {
      const inputs = document.querySelectorAll(selector);
      for (const input of inputs) {
        if (input.offsetParent !== null && input.value === "") {
          input.focus();
          input.value = phoneNumber;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
          await sleep(300);
          return true;
        }
      }
    } catch {
      continue;
    }
  }
  return false;
}

/* ───────── Additional questions filling ───────── */

/**
 * Fill text/number input fields using additionalQuestions answers.
 * @param {Object} answers - Key-value pairs from settings.additionalQuestions.inputField
 */
async function fillInputFields(answers) {
  if (!answers || Object.keys(answers).length === 0) return;

  const formGroups = document.querySelectorAll(
    ".jobs-easy-apply-form-section__grouping, " +
    "[class*='form-component'], " +
    ".fb-dash-form-element"
  );

  for (const group of formGroups) {
    try {
      const label = group.querySelector("label, legend, span[class*='label']");
      if (!label) continue;

      const labelText = label.textContent.trim().toLowerCase();
      const input = group.querySelector(
        "input[type='text'], input[type='number'], input:not([type='hidden']):not([type='checkbox']):not([type='radio'])"
      );

      if (!input || input.value !== "") continue;
      if (input.offsetParent === null) continue; // Not visible

      // Find matching answer
      for (const [key, value] of Object.entries(answers)) {
        if (labelText.includes(key.toLowerCase())) {
          input.focus();
          input.value = String(value);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
          await sleep(200);
          break;
        }
      }
    } catch {
      continue;
    }
  }
}

/**
 * Handle dropdown/select fields.
 * @param {Object} answers
 */
async function fillDropdowns(answers) {
  if (!answers || Object.keys(answers).length === 0) return;

  const selects = document.querySelectorAll("select");
  for (const select of selects) {
    try {
      if (select.offsetParent === null) continue;
      if (select.value && select.value !== "") continue;

      const label = select.closest("[class*='form']")?.querySelector("label, legend");
      if (!label) continue;

      const labelText = label.textContent.trim().toLowerCase();

      for (const [key, value] of Object.entries(answers)) {
        if (labelText.includes(key.toLowerCase())) {
          const options = [...select.options];
          const match = options.find(
            (opt) =>
              opt.text.toLowerCase().includes(String(value).toLowerCase()) ||
              opt.value.toLowerCase().includes(String(value).toLowerCase())
          );
          if (match) {
            select.value = match.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            await sleep(200);
          }
          break;
        }
      }
    } catch {
      continue;
    }
  }
}

/**
 * Handle radio button questions.
 * @param {number} defaultOption - 1 for first option (Yes), 2 for second (No). 0 = skip.
 */
async function fillRadioButtons(defaultOption) {
  if (!defaultOption) return;

  const radioGroups = document.querySelectorAll("fieldset");
  for (const group of radioGroups) {
    try {
      const radios = group.querySelectorAll("input[type='radio']");
      if (radios.length === 0) continue;

      // Check if any is already selected
      const anyChecked = [...radios].some((r) => r.checked);
      if (anyChecked) continue;

      const index = Math.min(defaultOption - 1, radios.length - 1);
      if (radios[index]) {
        radios[index].click();
        await sleep(200);
      }
    } catch {
      continue;
    }
  }
}

/**
 * Handle checkbox questions.
 * @param {boolean|string} answerAll - true to check all, false to uncheck all, "" to skip
 */
async function fillCheckboxes(answerAll) {
  if (answerAll === "" || answerAll === undefined || answerAll === null) return;

  const checkboxes = document.querySelectorAll(
    ".jobs-easy-apply-form-section__grouping input[type='checkbox'], " +
    "[class*='form-component'] input[type='checkbox']"
  );

  for (const cb of checkboxes) {
    try {
      if (cb.offsetParent === null) continue;
      // Skip the "follow company" checkbox
      if (cb.id === "follow-company-checkbox") continue;

      if (answerAll === true && !cb.checked) {
        cb.click();
        await sleep(100);
      } else if (answerAll === false && cb.checked) {
        cb.click();
        await sleep(100);
      }
    } catch {
      continue;
    }
  }
}

/**
 * Collect unanswered/skipped questions for export.
 * @returns {Object[]} Array of { label, type, selector }
 */
function collectSkippedQuestions() {
  const skipped = [];

  const formGroups = document.querySelectorAll(
    ".jobs-easy-apply-form-section__grouping, " +
    "[class*='form-component']"
  );

  for (const group of formGroups) {
    try {
      const label = group.querySelector("label, legend, span[class*='label']");
      if (!label) continue;
      const labelText = label.textContent.trim();

      // Check text/number inputs
      const input = group.querySelector(
        "input[type='text'], input[type='number'], input:not([type='hidden']):not([type='checkbox']):not([type='radio'])"
      );
      if (input && input.value === "" && input.offsetParent !== null) {
        skipped.push({ label: labelText, type: "input", field: "text" });
        continue;
      }

      // Check selects
      const select = group.querySelector("select");
      if (select && !select.value && select.offsetParent !== null) {
        skipped.push({ label: labelText, type: "dropdown", field: "select" });
        continue;
      }

      // Check radio groups
      const radios = group.querySelectorAll("input[type='radio']");
      if (radios.length > 0 && ![...radios].some((r) => r.checked)) {
        skipped.push({ label: labelText, type: "radio", field: "radio" });
      }
    } catch {
      continue;
    }
  }
  return skipped;
}

/* ───────── Save job before apply ───────── */

async function saveJobBeforeApply() {
  try {
    const saveBtn = document.querySelector(
      "button[class*='jobs-save-button'], " +
      "button[aria-label*='Save']"
    );
    if (saveBtn && !saveBtn.classList.contains("jobs-save-button--saved")) {
      saveBtn.click();
      await sleep(500);
    }
  } catch {
    // Non-critical
  }
}

/* ───────── Unfollow company after apply ───────── */

async function handleFollowCompany(shouldFollow) {
  if (shouldFollow) return; // Default is to follow, so only act if we should unfollow

  try {
    const followCheckbox = document.querySelector(
      "label[for='follow-company-checkbox']"
    );
    if (followCheckbox) {
      followCheckbox.click();
      await sleep(300);
    }
  } catch {
    // Non-critical
  }
}

/* ───────── Multi-step form processor ───────── */

/**
 * Process a multi-step Easy Apply form.
 * @param {Object} settings - User settings
 * @param {boolean} dryRun - If true, don't submit
 * @returns {Promise<{ status: string, message: string }>}
 */
async function processMultiStepForm(settings, dryRun) {
  const maxSteps = 10; // Safety limit

  for (let step = 0; step < maxSteps; step++) {
    await randomDelay(1000, 2500);

    // Fill form fields on this step
    await chooseResume(settings.preferredCv || 1);
    await fillPhoneNumber(settings.phoneNumber || "");
    await fillInputFields(settings.additionalQuestions || {});
    await fillDropdowns(settings.additionalQuestions || {});
    await fillRadioButtons(settings.defaultRadioOption || 0);
    await fillCheckboxes(settings.answerAllCheckboxes);

    // Collect skipped questions if enabled
    if (settings.outputSkippedQuestions) {
      const skipped = collectSkippedQuestions();
      if (skipped.length > 0) {
        // Store for later export
        chrome.runtime.sendMessage({
          action: "SKIPPED_QUESTIONS",
          questions: skipped,
          url: window.location.href,
        });
      }
    }

    // Check for Submit button
    const submitBtn = document.querySelector(
      "button[aria-label='Submit application']"
    );
    if (submitBtn) {
      await handleFollowCompany(settings.followCompanies);

      if (dryRun) {
        return {
          status: "dry_run",
          message: "DRY RUN - Would submit application",
        };
      }
      submitBtn.click();
      await randomDelay(1000, 2000);
      return { status: "applied", message: "Successfully applied" };
    }

    // Check for Review button
    const reviewBtn = document.querySelector(
      "button[aria-label='Review your application']"
    );
    if (reviewBtn) {
      reviewBtn.click();
      await randomDelay(1000, 2500);
      continue;
    }

    // Check for Continue/Next button
    const continueBtn = document.querySelector(
      "button[aria-label='Continue to next step']"
    );
    if (continueBtn) {
      continueBtn.click();
      await randomDelay(1000, 2500);
      continue;
    }

    // No recognizable button found — stuck
    return {
      status: "cannot_apply",
      message: "Form navigation stuck at step " + (step + 1),
    };
  }

  return {
    status: "cannot_apply",
    message: "Exceeded maximum form steps",
  };
}

/* ───────── Main job processor ───────── */

/**
 * Process a single job: check filters, click Easy Apply, fill forms, submit.
 * Called by the service worker via message.
 * @param {Object} settings
 * @param {boolean} dryRun
 * @returns {Promise<{ status: string, message: string }>}
 */
async function processJob(settings, dryRun) {
  console.log("[EasyApply] processJob called on:", window.location.href);

  // Wait for the job page to actually render (LinkedIn SPA is slow)
  // Try waiting for ANY of these indicators that the page has loaded
  const pageReady = await waitForPageContent(15000);
  if (!pageReady) {
    console.warn("[EasyApply] Page did not fully render within timeout");
  }

  // Extra settle time for React hydration
  await randomDelay(1000, 2000);

  // Debug: log what we can see on the page
  const allButtons = document.querySelectorAll("button");
  const buttonTexts = [...allButtons]
    .map((b) => b.textContent.trim().substring(0, 50))
    .filter((t) => t.length > 0);
  console.log("[EasyApply] Found", allButtons.length, "buttons. Texts:", buttonTexts.slice(0, 15));

  // Get job properties
  const props = getJobProperties();
  const propsLabel = `${props.title} | ${props.company} | ${props.location}`;
  console.log("[EasyApply] Job properties:", propsLabel);

  // Check filters
  const filterResult = checkFilters(props, settings);
  if (filterResult.skip) {
    return { status: "blacklisted", message: `${propsLabel} - ${filterResult.reason}` };
  }

  // Save before apply if enabled
  if (settings.saveBeforeApply) {
    await saveJobBeforeApply();
  }

  // Find Easy Apply button
  const easyApplyBtn = findEasyApplyButton();
  console.log("[EasyApply] Easy Apply button found:", !!easyApplyBtn);

  if (!easyApplyBtn) {
    // Check if already applied
    const alreadyApplied = document.querySelector(
      ".jobs-s-apply__application-link, " +
      "[class*='applied-badge']"
    );
    if (alreadyApplied || document.body.textContent.includes("Applied")) {
      // Verify it's the applied state for this specific job
      const applyArea = document.querySelector(
        "div[class*='jobs-apply-button--top-card']"
      );
      if (applyArea && applyArea.textContent.includes("Applied")) {
        return { status: "already_applied", message: `${propsLabel} - Already applied` };
      }
    }

    // Log non-Easy Apply job if enabled
    if (settings.listNonEasyApplyJobsUrl) {
      chrome.runtime.sendMessage({
        action: "NON_EASY_APPLY_JOB",
        url: window.location.href,
        title: props.title,
        company: props.company,
      });
    }

    return {
      status: "cannot_apply",
      message: `${propsLabel} - No Easy Apply button found`,
    };
  }

  // Click Easy Apply
  easyApplyBtn.click();
  await randomDelay(1500, 3000);

  // Handle the extra "Continue to next step" LinkedIn sometimes shows
  try {
    const extraContinue = document.querySelector(
      "button[aria-label='Continue to next step']"
    );
    if (extraContinue && extraContinue.offsetParent !== null) {
      extraContinue.click();
      await randomDelay(1000, 2000);
    }
  } catch {
    // Not always present
  }

  // Try single-step submit first
  await chooseResume(settings.preferredCv || 1);
  await fillPhoneNumber(settings.phoneNumber || "");
  await fillInputFields(settings.additionalQuestions || {});
  await fillDropdowns(settings.additionalQuestions || {});
  await fillRadioButtons(settings.defaultRadioOption || 0);
  await fillCheckboxes(settings.answerAllCheckboxes);

  const submitBtn = document.querySelector(
    "button[aria-label='Submit application']"
  );

  if (submitBtn) {
    await handleFollowCompany(settings.followCompanies);

    if (dryRun) {
      return { status: "dry_run", message: `${propsLabel} - DRY RUN` };
    }
    submitBtn.click();
    await randomDelay(1000, 2000);
    return { status: "applied", message: `${propsLabel} - Applied` };
  }

  // Multi-step form
  const result = await processMultiStepForm(settings, dryRun);
  result.message = `${propsLabel} - ${result.message}`;
  return result;
}

/* ───────── Message listener ───────── */

function _jobApplierListener(msg, sender, sendResponse) {
  if (msg.action === "PROCESS_JOB") {
    console.log("[EasyApply] PROCESS_JOB received");
    processJob(msg.settings || {}, msg.dryRun || false).then(sendResponse);
    return true; // Keep channel open for async response
  }
  // Let jobScanner.js handle other messages
  return false;
}

window.__jobApplierListener = _jobApplierListener;
chrome.runtime.onMessage.addListener(_jobApplierListener);
console.log("[EasyApply] jobApplier.js loaded on:", window.location.href);

}  // end block scope
