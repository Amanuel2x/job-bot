# Running the Internship Bot on Windows

## One-time setup

**1. Install Python**
Download from python.org — make sure to check "Add Python to PATH" during install.

**2. Copy the folder to your PC**
Transfer the entire `internship-bot` folder to your Windows machine.
Easiest options: USB drive, AirDrop to iCloud then download, or zip and email it to yourself.

**3. Open Command Prompt in the folder**
Navigate to the folder in File Explorer, click the address bar, type `cmd`, hit Enter.

**4. Create virtual environment and install dependencies**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**5. Set up your .env file**
```
copy .env.example .env
notepad .env
```
Fill in:
- `GMAIL_USER` = amanuelalexabu@gmail.com
- `GMAIL_APP_PASSWORD` = your 16-character app password (see below)
- `ANTHROPIC_API_KEY` = your Claude API key (optional)

**6. Add your resume**
Drop your resume PDF into the folder and name it `resume.pdf`.

---

## Gmail App Password (required for email digest)

1. Go to myaccount.google.com
2. Security → 2-Step Verification (turn it on if not already)
3. Search "App Passwords" at the top
4. Name it "Internship Bot" → Generate
5. Copy the 16-character password into your .env file

---

## Running overnight

**Option A — Run once manually**
```
venv\Scripts\activate
python main.py
```
This scrapes, matches, opens applications, and emails you a digest. Takes 5-10 minutes.

**Option B — Schedule it to run automatically every night**
Open Task Scheduler (search it in Start menu):
1. Create Basic Task
2. Name: "Internship Bot"
3. Trigger: Daily, set a time (e.g. 11:00 PM)
4. Action: Start a program
5. Program: `C:\path\to\internship-bot\venv\Scripts\python.exe`
6. Arguments: `main.py`
7. Start in: `C:\path\to\internship-bot`

Now it runs every night while you sleep and emails you what it did.

---

## What happens each run

1. Scrapes SimplifyJobs (4,500+ listings), LinkedIn, Wellfound, and New Grad positions
2. Filters to only Bay Area local, remote, or listings with housing/stipend
3. Scores every listing against your skill profile
4. Opens the top 150 matches in your browser (they stay as tabs for you to review)
5. Saves a cover letter for each one to manual_queue.json
6. Emails a full report to amanuelalexabu@gmail.com

---

## Hitting 100-200 applications per day

The bot opens 150 tabs per run by default. To actually submit them:

1. **Install the Simplify browser extension** — simplify.jobs
   - It autofills your name, email, resume, phone on most job applications
   - With 150 tabs open you can click through them fast

2. **Run the bot twice a day** — once in the morning, once at night
   - Morning run catches newly posted jobs
   - Night run catches afternoon postings
   - That's 300 tabs total — realistically 100-200 actual submissions

3. **Bottleneck is manual submission** — the bot can't submit for you on most platforms
   because they use captchas and login walls. But it does all the finding and sorting.
   Your job is just to click Apply on the ones it opens.

---

## Checking your progress

```
venv\Scripts\activate
python main.py --report
```

Or just check your Gmail — you'll get a formatted report after every run.
