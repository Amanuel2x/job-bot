# Internship Bot

Finds software engineering internships you're qualified for and mass-applies.
Completely standalone — no dependencies on Vera or any other project.

## Setup (one time)

```bash
cd ~/internship-bot

# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your info
cp .env.example .env
# Edit .env — fill in your name, email, phone, LinkedIn, GitHub, resume path

# 4. Edit profile.py
# Update your name, school, preferred locations, etc.
# Projects and skills are already pre-filled from your real work

# 5. Add your resume PDF as resume.pdf in this folder

# 6. (Optional) Add your Claude API key to .env for AI cover letters
#    ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
source venv/bin/activate

# See what you'd be applying to (no browser tabs opened)
python main.py --dry-run

# Scrape + match only, save to matches.json
python main.py --scrape-only

# Full run: scrape → match → open top 20 applications in browser
python main.py

# Apply from saved matches (after reviewing matches.json)
python main.py --apply-only

# Check your stats
python main.py --report
```

## How it works

1. **Scraper** (`scraper.py`) — pulls from:
   - SimplifyJobs GitHub repo (4,500+ community-maintained internship listings, most accurate)
   - LinkedIn public job search (no login required)
   - Indeed (currently blocked by 403, but included for future use)

2. **Matcher** (`matcher.py`) — scores each listing 0-100 against your skill profile:
   - Role title match (+30)
   - Skill keyword overlap (+40 max)
   - Preferred tech keywords (+20 max)
   - Remote bonus (+10)

3. **Applier** (`applier.py`) — opens the top N matched jobs in your browser:
   - SimplifyJobs links work great with the [Simplify browser extension](https://simplify.jobs) for 1-click autofill
   - LinkedIn links open the job posting directly
   - All applications logged to `applied.json` (no duplicates)
   - Cover letters (with or without Claude API) saved to `manual_queue.json`

## Files

| File | Purpose |
|------|---------|
| `profile.py` | Your skills, projects, preferences — edit this |
| `.env` | Your personal info + API keys — never commit this |
| `matches.json` | Latest matched job listings |
| `applied.json` | Log of every job you've applied to |
| `manual_queue.json` | Cover letters for each job |
| `resume_draft.md` | Resume draft based on your projects |

## Tips

- Install the [Simplify browser extension](https://simplify.jobs) — it autofills applications from your resume. Combined with this bot opening the tabs, you can apply to 50+ jobs in an hour.
- Adjust `MIN_MATCH_SCORE` in `.env` to control quality vs. quantity (25 = broad, 40 = focused)
- Run `--dry-run` first to review what you'd be applying to
- The bot logs everything — you'll never apply to the same job twice

## Resume

See `resume_draft.md` for a pre-written resume draft based on your real projects.
