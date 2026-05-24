/**
 * Content script — Job list scanner.
 * Runs on LinkedIn job search and job view pages.
 * Responds to messages from the service worker.
 */

// Remove old listener if re-injected
if (window.__jobScannerListener) {
  chrome.runtime.onMessage.removeListener(window.__jobScannerListener);
}

{  // Block scope to avoid redeclaration errors on re-injection

/* ───────── DOM helpers ───────── */

/**
 * Wait for an element to appear in the DOM.
 * @param {string} selector - CSS selector
 * @param {number} timeoutMs - Max wait time
 * @param {Element} parent - Parent element to search within
 * @returns {Promise<Element|null>}
 */
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

/**
 * Wait for multiple elements matching a selector.
 * @param {string} selector
 * @param {number} timeoutMs
 * @returns {Promise<Element[]>}
 */
function waitForElements(selector, timeoutMs = 10000) {
  return new Promise((resolve) => {
    const existing = document.querySelectorAll(selector);
    if (existing.length > 0) return resolve([...existing]);

    const observer = new MutationObserver(() => {
      const els = document.querySelectorAll(selector);
      if (els.length > 0) {
        observer.disconnect();
        resolve([...els]);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    setTimeout(() => {
      observer.disconnect();
      resolve([...document.querySelectorAll(selector)]);
    }, timeoutMs);
  });
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function randomDelay(min = 2000, max = 5000) {
  return sleep(Math.floor(Math.random() * (max - min) + min));
}

/* ───────── Job scanning ───────── */

/**
 * Get total job count from the search results page.
 * LinkedIn shows it in a <small> element at the top.
 */
function getTotalJobs() {
  const smallEl = document.querySelector(
    ".jobs-search-results-list__subtitle"
  );
  if (!smallEl) {
    // Fallback to any <small> in job results
    const fallback = document.querySelector("small");
    if (!fallback) return 0;
    return parseJobCount(fallback.textContent);
  }
  return parseJobCount(smallEl.textContent);
}

function parseJobCount(text) {
  if (!text) return 0;
  // Extract number from strings like "1,234 results" or "25 jobs"
  const match = text.replace(/,/g, "").match(/(\d+)/);
  return match ? parseInt(match[1], 10) : 0;
}

/**
 * Extract job IDs from the current search results page.
 * Filters out already-applied jobs.
 * @param {Object} settings - User settings for blacklist filtering
 * @returns {string[]} Array of job ID strings
 */
function getJobIds(settings) {
  const jobCards = document.querySelectorAll("li[data-occludable-job-id]");
  const ids = [];

  for (const card of jobCards) {
    const rawId = card.getAttribute("data-occludable-job-id");
    if (!rawId) continue;

    const jobId = rawId.split(":").pop();

    // Skip already applied
    const appliedBadge = card.querySelector(
      ".job-card-container__footer-item--is-applied"
    );
    const appliedText = card.textContent.includes("Applied");
    if (appliedBadge || appliedText) continue;

    ids.push(jobId);
  }

  return ids;
}

/* ───────── Job property extraction ───────── */

/**
 * Extract job properties from a job view page.
 * @returns {Object} Job properties
 */
function getJobProperties() {
  const props = {
    title: "",
    company: "",
    location: "",
    workType: "",
    description: "",
    hiringManager: "",
    applicantCount: "",
  };

  // Job title — try multiple selectors, then fallback to first h1
  try {
    const titleSelectors = [
      "h1.job-details-jobs-unified-top-card__job-title",
      "h1[class*='job-title']",
      ".jobs-unified-top-card__job-title",
      "[class*='top-card'] h1",
      "[class*='topcard'] h1",
      "h1",
    ];
    for (const sel of titleSelectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 2) {
        props.title = el.textContent.trim();
        break;
      }
    }
  } catch { /* ignore */ }

  // Company name — try multiple selectors
  try {
    const companySelectors = [
      ".job-details-jobs-unified-top-card__company-name a",
      ".jobs-unified-top-card__company-name a",
      "[class*='company-name'] a",
      "[class*='top-card'] [class*='company'] a",
      "[class*='topcard'] [class*='company'] a",
      "[class*='job-details'] a[href*='/company/']",
    ];
    for (const sel of companySelectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 0) {
        props.company = el.textContent.trim();
        break;
      }
    }
  } catch { /* ignore */ }

  // Location
  try {
    const locSelectors = [
      ".job-details-jobs-unified-top-card__bullet",
      ".jobs-unified-top-card__bullet",
      "[class*='top-card'] [class*='bullet']",
      "[class*='topcard'] [class*='location']",
      "[class*='job-details'] [class*='location']",
    ];
    for (const sel of locSelectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 0) {
        props.location = el.textContent.trim();
        break;
      }
    }
  } catch { /* ignore */ }

  // Work type (Remote/On-site/Hybrid)
  try {
    const workTypeSpans = document.querySelectorAll(
      "span[class*='ui-label'][class*='accent'] span[aria-hidden='true']"
    );
    if (workTypeSpans.length > 0) {
      props.workType = [...workTypeSpans].map((s) => s.textContent.trim()).join(" | ");
    }
  } catch { /* ignore */ }

  // Job description
  try {
    const descSelectors = [
      ".jobs-description__content",
      ".jobs-box__html-content",
      "[class*='description__text']",
      "[class*='job-details'] [class*='description']",
      "#job-details",
    ];
    for (const sel of descSelectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 20) {
        props.description = el.textContent.trim();
        break;
      }
    }
  } catch { /* ignore */ }

  // Hiring manager
  try {
    const hiringSelectors = [
      ".jobs-poster__name",
      ".hirer-card__hirer-information a",
      "[class*='hirer'] a",
      "[class*='poster'] [class*='name']",
    ];
    for (const sel of hiringSelectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim().length > 0) {
        props.hiringManager = el.textContent.trim();
        break;
      }
    }
  } catch { /* ignore */ }

  // Applicant count
  try {
    const appSelectors = [
      ".jobs-unified-top-card__applicant-count",
      "[class*='applicant-count']",
      "[class*='applicant']",
    ];
    for (const sel of appSelectors) {
      const el = document.querySelector(sel);
      if (el) {
        const match = el.textContent.replace(/,/g, "").match(/(\d+)/);
        if (match) {
          props.applicantCount = parseInt(match[1], 10);
          break;
        }
      }
    }
  } catch { /* ignore */ }

  console.log("[EasyApply] getJobProperties:", props.title, "|", props.company, "|", props.location);
  return props;
}

/* ───────── Blacklist / whitelist checks ───────── */

/**
 * Check if a job should be skipped based on filters.
 * Implements both free features (blacklist) and Pro features (whitelists, hiring manager, etc.)
 * @param {Object} props - Job properties
 * @param {Object} settings - User settings
 * @returns {{ skip: boolean, reason: string }}
 */
function checkFilters(props, settings) {
  const title = (props.title || "").toLowerCase();
  const company = (props.company || "").toLowerCase();
  const description = (props.description || "").toLowerCase();
  const hiringManager = (props.hiringManager || "").toLowerCase();
  const applicantCount =
    typeof props.applicantCount === "number" ? props.applicantCount : 0;

  // Blacklist companies
  const blacklistCompanies = (settings.blacklistCompanies || []).map((c) =>
    c.toLowerCase()
  );
  if (blacklistCompanies.some((bc) => company.includes(bc))) {
    return { skip: true, reason: "Blacklisted company: " + props.company };
  }

  // Blacklist titles
  const blackListTitles = (settings.blackListTitles || []).map((t) =>
    t.toLowerCase()
  );
  if (blackListTitles.some((bt) => title.includes(bt))) {
    return { skip: true, reason: "Blacklisted title keyword: " + props.title };
  }

  // --- Pro features ---

  // Only apply to specific companies
  const onlyCompanies = (settings.onlyApplyCompanies || []).map((c) =>
    c.toLowerCase()
  );
  if (onlyCompanies.length > 0 && !onlyCompanies.some((c) => company.includes(c))) {
    return { skip: true, reason: "Not in onlyApplyCompanies list" };
  }

  // Only apply to titles with keywords
  const onlyTitles = (settings.onlyApplyTitles || []).map((t) =>
    t.toLowerCase()
  );
  if (onlyTitles.length > 0 && !onlyTitles.some((t) => title.includes(t))) {
    return { skip: true, reason: "Not in onlyApplyTitles list" };
  }

  // Block hiring manager
  const blockHiring = (settings.blockHiringMember || []).map((h) =>
    h.toLowerCase()
  );
  if (blockHiring.length > 0 && blockHiring.some((h) => hiringManager.includes(h))) {
    return { skip: true, reason: "Blocked hiring manager: " + props.hiringManager };
  }

  // Only apply hiring manager
  const onlyHiring = (settings.onlyApplyHiringMember || []).map((h) =>
    h.toLowerCase()
  );
  if (onlyHiring.length > 0 && !onlyHiring.some((h) => hiringManager.includes(h))) {
    return { skip: true, reason: "Not in onlyApplyHiringMember list" };
  }

  // Max applications filter
  const maxApps = parseInt(settings.onlyApplyMaxApplications || "0", 10);
  if (maxApps > 0 && applicantCount > maxApps) {
    return {
      skip: true,
      reason: `Too many applicants (${applicantCount} > ${maxApps})`,
    };
  }

  // Min applications filter
  const minApps = parseInt(settings.onlyApplyMinApplications || "0", 10);
  if (minApps > 0 && applicantCount < minApps) {
    return {
      skip: true,
      reason: `Too few applicants (${applicantCount} < ${minApps})`,
    };
  }

  // Job description keyword filters
  const onlyDescKeywords = (settings.onlyApplyJobDescription || []).map((k) =>
    k.toLowerCase()
  );
  if (
    onlyDescKeywords.length > 0 &&
    !onlyDescKeywords.some((k) => description.includes(k))
  ) {
    return { skip: true, reason: "Job description missing required keywords" };
  }

  const blockDescKeywords = (settings.blockJobDescription || []).map((k) =>
    k.toLowerCase()
  );
  if (blockDescKeywords.some((k) => description.includes(k))) {
    return { skip: true, reason: "Job description contains blocked keywords" };
  }

  return { skip: false, reason: "" };
}

/* ───────── Message listener ───────── */

function _jobScannerListener(msg, sender, sendResponse) {
  switch (msg.action) {
    case "GET_TOTAL_JOBS": {
      console.log("[EasyApply] GET_TOTAL_JOBS received");
      const totalJobs = getTotalJobs();
      console.log("[EasyApply] Total jobs found:", totalJobs);
      sendResponse({ totalJobs });
      break;
    }

    case "GET_JOB_IDS": {
      console.log("[EasyApply] GET_JOB_IDS received");
      const jobIds = getJobIds(msg.settings || {});
      console.log("[EasyApply] Job IDs found:", jobIds.length);
      sendResponse({ jobIds });
      break;
    }

    case "GET_JOB_PROPERTIES": {
      const props = getJobProperties();
      sendResponse(props);
      break;
    }

    case "CHECK_FILTERS": {
      const properties = getJobProperties();
      const filterResult = checkFilters(properties, msg.settings || {});
      sendResponse({ ...filterResult, properties });
      break;
    }

    // PROCESS_JOB is handled by jobApplier.js — see that file
    default:
      return false;
  }
  return true;
}

window.__jobScannerListener = _jobScannerListener;
chrome.runtime.onMessage.addListener(_jobScannerListener);
console.log("[EasyApply] jobScanner.js loaded on:", window.location.href);

}  // end block scope
