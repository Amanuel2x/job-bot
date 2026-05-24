# Job Bot

Finds software engineering jobs you're qualified for and mass-applies. Two components work together:

| Component | What it does |
|-----------|-------------|
| **Python bot** (`/`) | Scrapes job listings, scores them against your profile, and opens the top matches in your browser |
| **Chrome extension** (`EasyApplyJobsBot/extension/`) | Sits in your browser and auto-fills + submits LinkedIn Easy Apply forms |

---

## Python Bot Setup

### 1. Clone and create virtualenv

```bash
git clone https://github.com/Amanuel2x/job-bot.git
cd job-bot

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure your info

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | What to put |
|----------|-------------|
| `FULL_NAME` | Your full name |
| `EMAIL` | Your email |
| `PHONE` | Your phone number |
| `LINKEDIN` | Your LinkedIn URL |
| `RESUME_PATH` | Path to your resume PDF (default: `./resume.pdf`) |
| `ANTHROPIC_API_KEY` | (Optional) Claude API key for AI cover letters — get one at [console.anthropic.com](https://console.anthropic.com) |
| `TELEGRAM_BOT_TOKEN` | (Optional) Telegram bot token for run notifications |
| `TELEGRAM_CHAT_ID` | (Optional) Your Telegram chat ID |
| `MIN_MATCH_SCORE` | Minimum score to apply — 25 = broad, 40 = focused |
| `APPLY_LIMIT_PER_RUN` | Max tabs to open per run (default: 150) |

### 3. Edit your profile

Open `profile.py` and update your name, school, skills, and preferred locations. Projects and skills are pre-filled — adjust to match your resume.

### 4. Add your resume

Drop your resume as `resume.pdf` in the project root.

### 5. (Optional) Telegram notifications

1. Open Telegram, search `@BotFather`
2. Send `/newbot`, give it any name
3. Copy the token into `TELEGRAM_BOT_TOKEN`
4. Message your bot once, then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Copy the `id` from the `chat` object into `TELEGRAM_CHAT_ID`

---

## Python Bot Usage

```bash
source venv/bin/activate

# Preview what you'd be applying to (no tabs opened)
python main.py --dry-run

# Scrape + score only — saves to matches.json
python main.py --scrape-only

# Full run: scrape → score → open top N jobs in browser
python main.py

# Apply from saved matches (after reviewing matches.json)
python main.py --apply-only

# Stats report
python main.py --report
```

**Tip:** Run `--dry-run` first, review `matches.json`, then run `--apply-only` to open only the jobs you want.

---

## Chrome Extension Setup

The extension handles LinkedIn Easy Apply forms — it clicks through multi-step applications, fills in your answers, and submits automatically.

### Install in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right)
3. Click **Load unpacked**
4. Select the `EasyApplyJobsBot/extension/` folder from this repo
5. The extension icon will appear in your toolbar

### Configure the extension

Click the extension icon to open the settings panel. Key tabs:

**Search tab**
- Set keywords (e.g. `software engineer, backend, python`)
- Set locations (e.g. `NorthAmerica`, `Remote`)
- Select experience levels — check `Internship` and `Entry level`
- Set date posted, job type, and work location filters

**Form Fill tab**
- Add your phone number
- Set `Preferred CV` to `1` (first uploaded resume on LinkedIn)
- Fill in `Additional Questions` — one per line as `Key: Value`, e.g.:
  ```
  Python: 3
  React: 2
  Salary expectations: 80000
  GPA: 3.5
  ```

**Advanced tab**
- Enable **AI Form Filling** and paste your Anthropic API key to let Claude answer unknown questions
- Set your profile context in the text box so the AI has accurate info
- Enable **Dry Run** to simulate without submitting (good for testing)
- Set **Max Applications Per Run** to cap how many it submits

**Filters tab**
- Blacklist companies or title keywords you want to skip
- Set required description keywords to only apply to matching roles

### Run the bot

1. Go to [linkedin.com/jobs](https://www.linkedin.com/jobs) (you must be logged in)
2. Click the extension icon
3. Hit **Save Settings**, then **Start**
4. The bot opens job listings in a new tab and starts applying

Results are logged in the **Results tab** and can be exported as CSV or JSON.

---

## How the Python Bot Works

1. **Scraper** (`scraper.py`) pulls from:
   - [SimplifyJobs GitHub repo](https://github.com/SimplifyJobs/Summer2025-Internships) — 4,500+ community-maintained listings
   - LinkedIn public job search
   - Indeed (currently 403'd, included for future use)

2. **Matcher** (`matcher.py`) scores each listing 0–100:
   - Role title match (+30)
   - Skill keyword overlap (+40 max)
   - Preferred tech keywords (+20 max)
   - Remote bonus (+10)

3. **Applier** (`applier.py`) opens the top N jobs in your browser:
   - SimplifyJobs links work great with the [Simplify extension](https://simplify.jobs) for 1-click autofill
   - All applications logged to `applied.json` — no duplicate applies

---

## Files Reference

| File | Purpose |
|------|---------|
| `profile.py` | Your skills, projects, preferences — edit this |
| `.env` | Personal info + API keys — never committed |
| `matches.json` | Latest scored job listings |
| `applied.json` | Log of every job applied to |
| `EasyApplyJobsBot/extension/` | Chrome extension source |
| `EasyApplyJobsBot/extension/manifest.json` | Extension config |
| `EasyApplyJobsBot/extension/background/service-worker.js` | Bot orchestration logic |
| `EasyApplyJobsBot/extension/popup/` | Settings UI |
| `EasyApplyJobsBot/extension/content/` | Page interaction scripts |

---

## Tips

- Install [Simplify](https://simplify.jobs) alongside this — it autofills applications from your resume. Combined with the Python bot opening tabs, you can cover 50+ jobs in an hour.
- Use `MIN_MATCH_SCORE=25` for quantity, `40` for quality.
- The extension's Dry Run mode is useful for verifying form-fill behavior before committing to real submissions.
- The bot never applies to the same job twice — `applied.json` and `linkedin_applied.json` track everything.
