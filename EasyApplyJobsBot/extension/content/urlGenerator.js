/**
 * LinkedIn job search URL generator.
 * Direct port of LinkedinUrlGenerate from utils.py.
 */

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
  Internship: "1",
  "Entry level": "2",
  Associate: "3",
  "Mid-Senior level": "4",
  Director: "5",
  Executive: "6",
};

const JOB_TYPE_CODES = {
  "Full-time": "F",
  "Part-time": "P",
  Contract: "C",
  Temporary: "T",
  Volunteer: "V",
  Intership: "I",
  Other: "O",
};

const REMOTE_CODES = {
  "On-site": "1",
  Remote: "2",
  Hybrid: "3",
};

const SALARY_CODES = {
  "$40,000+": "1",
  "$60,000+": "2",
  "$80,000+": "3",
  "$100,000+": "4",
  "$120,000+": "5",
  "$140,000+": "6",
  "$160,000+": "7",
  "$180,000+": "8",
  "$200,000+": "9",
};

const SORT_CODES = {
  Recent: "DD",
  Relevent: "R",
};

const DATE_POSTED_SECONDS = {
  "Any Time": "",
  "Past Month": "r2592000",
  "Past Week": "r604800",
  "Past 24 hours": "r86400",
};

/**
 * Build a multi-value URL parameter.
 * First value uses the prefix (e.g., "&f_E=2"), subsequent values use "%2C" separator.
 * @param {string[]} values - Array of human-readable values
 * @param {Object} codeMap - Map from human-readable to URL code
 * @param {string} paramName - URL parameter name (e.g., "f_E")
 * @returns {string}
 */
function buildMultiValueParam(values, codeMap, paramName) {
  if (!values || values.length === 0) return "";

  const codes = values.map((v) => codeMap[v]).filter(Boolean);
  if (codes.length === 0) return "";

  return "&" + paramName + "=" + codes.join("%2C");
}

/**
 * Generate LinkedIn job search URLs from settings.
 * @param {Object} settings - User settings from chrome.storage
 * @returns {string[]} Array of search URLs
 */
function generateSearchUrls(settings) {
  const locations = settings.location || [];
  const keywords = settings.keywords || [];
  const urls = [];

  for (const location of locations) {
    for (const keyword of keywords) {
      let url = LINKEDIN_JOB_SEARCH_URL + "?f_AL=true";
      url += "&keywords=" + encodeURIComponent(keyword);

      // Job type
      url += buildMultiValueParam(settings.jobType, JOB_TYPE_CODES, "f_JT");

      // Remote
      url += buildMultiValueParam(settings.remote, REMOTE_CODES, "f_WT");

      // Location + geoId
      url += "&location=" + encodeURIComponent(location);
      const geoId = GEO_IDS[location.toLowerCase().replace(/\s+/g, "")];
      if (geoId) {
        url += "&geoId=" + geoId;
      }

      // Experience level
      url += buildMultiValueParam(
        settings.experienceLevels,
        EXPERIENCE_LEVEL_CODES,
        "f_E"
      );

      // Date posted
      const dateVal =
        DATE_POSTED_SECONDS[(settings.datePosted || [])[0]] || "";
      if (dateVal) {
        url += "&f_TPR=" + dateVal;
      }

      // Salary
      const salaryCode = SALARY_CODES[(settings.salary || [])[0]] || "";
      if (salaryCode) {
        url += "&f_SB2=" + salaryCode;
      }

      // Sort
      const sortCode = SORT_CODES[(settings.sort || [])[0]] || "";
      if (sortCode) {
        url += "&sortBy=" + sortCode;
      }

      urls.push(url);
    }
  }

  return urls;
}

// Export for use in service worker (ES module) and content scripts
if (typeof globalThis !== "undefined") {
  globalThis.generateSearchUrls = generateSearchUrls;
}
