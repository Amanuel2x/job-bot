# LinkedIn Easy Apply Bot - Chrome Extension

A Chrome extension that automates LinkedIn Easy Apply job applications with configurable filters, multi-step form handling, and AI-powered question answering.

## What It Does

- Searches LinkedIn jobs based on your keywords, location, and filters
- Automatically applies to Easy Apply jobs
- Fills multi-step application forms (phone, resume, additional questions)
- Uses OpenAI to answer unknown form questions
- Tracks all applications with real-time stats and CSV/JSON export

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YourUsername/EasyApplyJobsBot.git
   ```
2. Open Chrome and go to `chrome://extensions/`
3. Enable **Developer mode** (top right toggle)
4. Click **Load unpacked**
5. Select the `extension/` folder from the cloned repo

## Setup

Click the extension icon in your Chrome toolbar to open the settings popup.

### Search Tab
- **Keywords**: Job search terms (comma-separated) — e.g., `AI Engineer, ML Engineer`
- **Locations**: Where to search — e.g., `USA, Europe`
- **Experience Level**: Internship, Entry, Associate, Mid-Senior, Director, Executive
- **Date Posted**: Any Time, Past Month, Past Week, Past 24 hours
- **Job Type**: Full-time, Part-time, Contract, Temporary
- **Work Location**: On-site, Remote, Hybrid
- **Salary**: Minimum salary filter
- **Sort**: Most Recent or Most Relevant

### Filters Tab
- **Blacklist Companies**: Skip jobs from these companies
- **Blacklist Title Keywords**: Skip jobs with these words in the title
- **Only Apply Companies**: Only apply to these companies (leave empty for all)
- **Only Apply Title Keywords**: Only apply to jobs with these title keywords
- **Block/Only Hiring Managers**: Filter by hiring manager name
- **Max/Min Applicants**: Skip jobs with too many or too few applicants
- **Description Keywords**: Require or block keywords in job descriptions

### Form Fill Tab
- **Phone Number**: Auto-fill phone fields
- **Preferred CV**: Which resume to select (1 = first, 2 = second)
- **Default Radio Option**: Auto-answer radio buttons (1 = Yes, 2 = No)
- **Additional Questions**: Key-value pairs for form fields (e.g., `Python: 5`)

### Advanced Tab

#### AI Form Filling (OpenAI)
When enabled, the bot uses OpenAI to answer form questions it can't fill from your static answers.

- **Enable AI**: Check to activate
- **OpenAI API Key**: Your `sk-...` key
- **Model**: GPT-4o Mini (cheapest, ~$0.001/question) or GPT-4o
- **Your Profile Context**: Information about you that the AI uses to answer questions:
  ```
  Name: John Doe
  Location: New York, USA
  Experience: 5 years AI/ML
  Skills: Python, PyTorch, TensorFlow
  Visa: No sponsorship needed
  Salary: $120k-$150k
  ```

#### Other Settings
- **Dry Run**: Simulate without submitting (test your settings first)
- **Max Applications Per Run**: Cap total applications (0 = unlimited)
- **Follow Companies**: Follow/unfollow after applying
- **Save Before Apply**: Save job before applying

### Results Tab
- Real-time log of all actions (applied, skipped, blacklisted, errors)
- Export to CSV or JSON
- Session stats: jobs processed, applied, blacklisted, duration

## How It Works

### Architecture

```
Popup (Settings UI)
    ↓ saves to chrome.storage.sync
Service Worker (Orchestrator)
    ↓ generates search URLs
    ↓ navigates LinkedIn tab
    ↓ executes scripts in tab via chrome.scripting.executeScript
LinkedIn Tab
    ↓ extracts job data, clicks Easy Apply
    ↓ navigates to /apply URL
    ↓ fills forms step by step
    ↓ submits application
Service Worker
    ↓ logs results, updates stats
    ↓ moves to next job
```

### Flow

1. **Generate URLs** — Builds LinkedIn search URLs from your settings
2. **Scan search results** — Extracts job IDs from each results page
3. **Visit each job** — Navigates to the job view page
4. **Check filters** — Verifies title/company against blacklists and whitelists
5. **Click Easy Apply** — Finds the apply link and extracts the apply URL
6. **Navigate to apply page** — Opens the application form directly
7. **Fill form** — Fills phone, resume, additional questions, radio buttons
8. **AI fallback** — If fields are unfilled and AI is enabled, asks OpenAI
9. **Submit** — Clicks through Continue → Review → Submit
10. **Log result** — Records outcome and moves to next job

### Key Technical Decisions

- **No content scripts** — Uses `chrome.scripting.executeScript` exclusively. Each function runs fresh in the tab context, avoiding stale DOM issues.
- **Direct URL navigation** — Instead of clicking the Easy Apply `<a>` tag (which LinkedIn's JS intercepts), the bot extracts the `href` and navigates directly.
- **Humanized delays** — Random 2-5 second delays between actions.
- **Resilient selectors** — Multiple fallback strategies for finding elements (aria-label, class, text content, tag scanning).

## Project Structure

```
extension/
├── manifest.json              # MV3 manifest
├── background/
│   └── service-worker.js      # Bot orchestration, OpenAI integration
├── popup/
│   ├── popup.html             # Settings UI
│   ├── popup.css              # Styles
│   └── popup.js               # Settings save/load, controls
├── options/
│   └── options.html           # Options page
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── content/                   # (Legacy, not used in current architecture)
    ├── jobScanner.js
    ├── jobApplier.js
    └── urlGenerator.js
```

## Original Python Bot

The `extension/` directory contains the Chrome extension. The root directory still contains the original Python/Selenium bot files (`linkedin.py`, `config.py`, `utils.py`, etc.) for reference.

## Disclaimer

This tool automates actions on LinkedIn, which may violate LinkedIn's Terms of Service. Use at your own risk. The authors are not responsible for any account restrictions or bans. Recommended to use with a secondary account for testing.

## License

MIT
