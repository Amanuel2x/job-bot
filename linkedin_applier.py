"""
LinkedIn Easy Apply bot — searches for CS/CE jobs and auto-applies.
Uses your existing Chrome profile (you must be logged into LinkedIn).
Close Chrome before running this.
"""

from __future__ import annotations
import json
import os
import random
import re
import time
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException,
    StaleElementReferenceException,
)
from dotenv import load_dotenv
import requests

load_dotenv()

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROFILE = {
    "first_name": "Amanuel",
    "last_name": "Abu",
    "full_name": "Amanuel Abu",
    "email": os.getenv("EMAIL", "amanuelalexabu@gmail.com"),
    "phone": os.getenv("PHONE", "(669) 292-8473"),
    "linkedin": "https://www.linkedin.com/in/amanuelabu",
    "github": "https://github.com/amanuel2x",
    "location": "San Francisco, CA",
    "university": "San Francisco State University",
    "degree": "Bachelor of Science",
    "major": "Computer Science",
    "gpa": "3.5",
    "grad_year": "2026",
    "resume_path": str(Path(__file__).parent / "Amanuel_Abu_Resume.pdf"),
}

APPLIED_LOG = Path(__file__).parent / "linkedin_applied.json"

# Search config — CS/CE jobs, Summer 2026, Easy Apply only
SEARCH_QUERIES = [
    "software engineer intern",
    "software engineering intern",
    "computer science intern",
    "SWE intern",
    "backend engineer intern",
    "frontend engineer intern",
    "full stack intern",
    "data engineer intern",
    "machine learning intern",
]

# LinkedIn search URL params
SEARCH_PARAMS = {
    "f_AL": "true",      # Easy Apply only
    "f_E": "1",          # Experience: Job
    "f_TPR": "r2592000", # Posted in last month
    "sortBy": "DD",      # Newest first
}

# Locations to search
SEARCH_LOCATIONS = [
    ("San Francisco Bay Area", "90000084"),
    ("United States", "103644278"),
]

MAX_APPLICATIONS = int(os.getenv("LINKEDIN_APPLY_LIMIT", "100"))
MAX_PER_COMPANY = 3

# Applicant context for Claude
_APPLICANT_CONTEXT = """
You are filling out a LinkedIn Easy Apply job application for Amanuel Abu:
- CS student at San Francisco State University, graduating May 2026
- Location: San Francisco, CA
- Phone: (669) 292-8473
- Email: amanuelalexabu@gmail.com
- GitHub: https://github.com/amanuel2x
- LinkedIn: https://www.linkedin.com/in/amanuelabu
- Gender: Male | Race: Black or African American | Not Hispanic/Latino
- Disability: No | Veteran: No | Sexual Orientation: Heterosexual | Pronouns: He/Him
- Work authorization: Yes | Sponsorship needed: No
- Available: June 2026 | Willing to relocate: Yes | Open to remote: Yes
- Years of experience: 1 | GPA: 3.5

Rules:
- Keep answers SHORT (1-3 words for dropdowns).
- For Yes/No questions about authorization: Yes. Sponsorship: No.
- For experience/years: 1 or 0.
- For salary: leave blank or say "Open".
- For start date: June 2026.
- NEVER choose "Decline" — always give a real answer.
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pause(lo=1.0, hi=2.5):
    time.sleep(random.uniform(lo, hi))


def _telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def _load_applied() -> dict:
    if APPLIED_LOG.exists():
        return json.loads(APPLIED_LOG.read_text())
    return {}


def _save_applied(data: dict):
    APPLIED_LOG.write_text(json.dumps(data, indent=2))


def _ask_claude(question: str, options: list[str] = None) -> str:
    """Ask Claude to answer a form question."""
    if not _HAS_ANTHROPIC or not ANTHROPIC_API_KEY:
        return options[0] if options else "Yes"

    opts_text = f"\nOptions: {', '.join(options)}" if options else ""
    prompt = (
        f"{_APPLICANT_CONTEXT}\n\n"
        f"Answer this form question. Reply with ONLY the answer, nothing else.{opts_text}\n\n"
        f"Question: {question}"
    )
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return options[0] if options else "Yes"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

LINKEDIN_PROFILE_DIR = str(Path(__file__).parent / ".linkedin_chrome_profile")


def _make_driver():
    """Launch Chrome with anti-detection for LinkedIn."""
    from webdriver_manager.chrome import ChromeDriverManager
    import glob

    options = Options()
    options.add_argument(f"--user-data-dir={LINKEDIN_PROFILE_DIR}")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    wdm_path = ChromeDriverManager().install()
    driver_dir = str(Path(wdm_path).parent)
    candidates = glob.glob(f"{driver_dir}/chromedriver*")
    binary = next(
        (p for p in candidates if not p.endswith(".chromedriver") and "NOTICE" not in p and Path(p).is_file()),
        wdm_path,
    )
    service = Service(binary)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(3)
    return driver


def _wait_for_login(driver):
    """Navigate to LinkedIn and wait for user to log in manually if needed."""
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(3)

    if "/login" in driver.current_url or "/authwall" in driver.current_url:
        driver.get("https://www.linkedin.com/login")
        print("\n  *** Log into LinkedIn in the Chrome window that just opened ***")
        print("  *** The bot will continue automatically once you're logged in ***\n")
        # Wait up to 5 minutes for user to log in
        for _ in range(300):
            time.sleep(1)
            try:
                url = driver.current_url
                if "/feed" in url or "/jobs" in url or "/mynetwork" in url:
                    print("  Logged in! Starting applications...\n")
                    time.sleep(2)
                    return True
            except Exception:
                pass
        print("  Login timeout — please try again.")
        return False
    else:
        print("  Already logged in! Starting applications...\n")
        return True


# ---------------------------------------------------------------------------
# Form filling
# ---------------------------------------------------------------------------

def _fill_form_fields(driver, modal):
    """Fill all visible form fields on the current Easy Apply step."""
    p = PROFILE

    # Text inputs and textareas
    for inp in modal.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], input[type='email'], textarea"):
        try:
            if not inp.is_displayed() or not inp.is_enabled():
                continue
            val = inp.get_attribute("value") or ""
            if val.strip():
                continue  # already filled

            # Find label
            label = ""
            inp_id = inp.get_attribute("id") or ""
            if inp_id:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{inp_id}']").text.strip().lower()
                except Exception:
                    pass
            if not label:
                label = (inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or "").lower()

            # Match to profile
            answer = ""
            if "phone" in label or "mobile" in label:
                answer = p["phone"]
            elif "email" in label:
                answer = p["email"]
            elif "first name" in label:
                answer = p["first_name"]
            elif "last name" in label:
                answer = p["last_name"]
            elif "full name" in label or "name" == label:
                answer = p["full_name"]
            elif "linkedin" in label:
                answer = p["linkedin"]
            elif "github" in label or "portfolio" in label or "website" in label or "url" in label:
                answer = p["github"]
            elif "city" in label or "location" in label or "address" in label:
                answer = p["location"]
            elif "school" in label or "university" in label or "college" in label:
                answer = p["university"]
            elif "gpa" in label or "grade point" in label:
                answer = p["gpa"]
            elif "major" in label or "field of study" in label or "degree" in label:
                answer = p["major"]
            elif "graduat" in label:
                answer = "May 2026"
            elif "salary" in label or "compensation" in label or "pay" in label:
                answer = ""  # skip salary
            elif "experience" in label or "years" in label:
                answer = "1"
            elif label:
                answer = _ask_claude(label)

            if answer:
                inp.clear()
                inp.send_keys(answer)
                _pause(0.2, 0.5)
        except (StaleElementReferenceException, ElementNotInteractableException):
            continue

    # Dropdowns (real <select> elements — LinkedIn uses these)
    for sel_el in modal.find_elements(By.TAG_NAME, "select"):
        try:
            if not sel_el.is_displayed():
                continue
            sel = Select(sel_el)
            current = sel.first_selected_option.text.strip()
            if current and current.lower() not in ("select an option", "select", "--", ""):
                continue  # already answered

            # Get label
            label = ""
            sel_id = sel_el.get_attribute("id") or ""
            if sel_id:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{sel_id}']").text.strip().lower()
                except Exception:
                    pass

            options = [o.text.strip() for o in sel.options if o.text.strip() and o.text.strip().lower() not in ("select an option", "select", "--")]

            # Match known answers
            answer = ""
            if "sponsor" in label or "visa" in label:
                answer = "No"
            elif "authorized" in label or "legally" in label or "eligible" in label:
                answer = "Yes"
            elif "gender" in label:
                answer = "Male"
            elif "race" in label or "ethnicity" in label:
                answer = "Black"
            elif "hispanic" in label or "latino" in label:
                answer = "No"
            elif "veteran" in label:
                answer = "No"
            elif "disability" in label:
                answer = "No"
            elif "education" in label or "degree" in label:
                answer = "Bachelor"
            elif label:
                answer = _ask_claude(label, options)

            if answer:
                for opt in sel.options:
                    if answer.lower() in opt.text.lower():
                        sel.select_by_visible_text(opt.text)
                        break
                else:
                    # Fallback: first non-empty option
                    if len(sel.options) > 1:
                        sel.select_by_index(1)
            _pause(0.2, 0.4)
        except Exception:
            continue

    # Radio buttons
    for fieldset in modal.find_elements(By.CSS_SELECTOR, "fieldset"):
        try:
            radios = fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if not radios or any(r.is_selected() for r in radios):
                continue  # already answered

            # Get question text
            legend = ""
            try:
                legend = fieldset.find_element(By.TAG_NAME, "legend").text.strip().lower()
            except Exception:
                try:
                    legend = fieldset.find_element(By.TAG_NAME, "span").text.strip().lower()
                except Exception:
                    pass

            # Find the right answer
            target = "yes"
            if "sponsor" in legend or "visa" in legend:
                target = "no"
            elif "commute" in legend or "relocate" in legend:
                target = "yes"

            for radio in radios:
                try:
                    rid = radio.get_attribute("id") or ""
                    lbl = fieldset.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.strip().lower()
                    if target in lbl:
                        driver.execute_script("arguments[0].click();", radio)
                        break
                except Exception:
                    continue
            else:
                # Default: click first radio
                if radios:
                    driver.execute_script("arguments[0].click();", radios[0])
            _pause(0.2, 0.4)
        except Exception:
            continue

    # Checkboxes (terms, acknowledgements — just check them)
    for cb in modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        try:
            if not cb.is_displayed():
                continue
            cb_id = cb.get_attribute("id") or ""
            if "follow" in cb_id.lower():
                # Uncheck "follow company"
                if cb.is_selected():
                    lbl = modal.find_element(By.CSS_SELECTOR, f"label[for='{cb_id}']")
                    driver.execute_script("arguments[0].click();", lbl)
            elif not cb.is_selected():
                # Check terms/consent boxes
                try:
                    lbl = modal.find_element(By.CSS_SELECTOR, f"label[for='{cb_id}']")
                    driver.execute_script("arguments[0].click();", lbl)
                except Exception:
                    driver.execute_script("arguments[0].click();", cb)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Easy Apply flow
# ---------------------------------------------------------------------------

def _apply_to_job(driver, job_card_el, job_id: str) -> str:
    """Click Easy Apply, fill multi-step form, submit. Returns status."""
    try:
        # Click the job card to load details
        driver.execute_script("arguments[0].click();", job_card_el)
        time.sleep(2)

        # Wait up to 5 seconds for the Easy Apply button to appear
        easy_btn = None
        for _ in range(10):
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                try:
                    txt = btn.text.strip()
                    cls = btn.get_attribute("class") or ""
                    if "Easy Apply" in txt and "jobs-apply" in cls and btn.is_displayed():
                        easy_btn = btn
                        break
                except (StaleElementReferenceException, Exception):
                    continue
            if easy_btn:
                break
            time.sleep(0.5)

        if not easy_btn:
            return "skipped"

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", easy_btn)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", easy_btn)
        time.sleep(2)

        # Wait for modal
        try:
            modal = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-easy-apply-modal, [class*='easy-apply-modal']"))
            )
        except TimeoutException:
            print("    No modal appeared")
            return "failed"

        # Multi-step form loop
        for step in range(10):
            _pause(1.0, 2.0)

            # Fill all fields on this step
            _fill_form_fields(driver, modal)

            # Handle resume upload if present
            for file_inp in modal.find_elements(By.CSS_SELECTOR, "input[type='file']"):
                try:
                    file_inp.send_keys(PROFILE["resume_path"])
                    _pause(1.5, 2.5)
                except Exception:
                    pass

            _pause(0.5, 1.0)

            # Find primary action button
            primary_btn = None
            for btn in modal.find_elements(By.CSS_SELECTOR, "button.artdeco-button--primary"):
                if btn.is_displayed():
                    primary_btn = btn
                    break

            if not primary_btn:
                print("    No primary button found")
                break

            btn_text = primary_btn.text.strip().lower()
            aria = (primary_btn.get_attribute("aria-label") or "").lower()

            if "submit" in btn_text or "submit" in aria:
                driver.execute_script("arguments[0].click();", primary_btn)
                _pause(2.0, 4.0)

                # Click Done
                try:
                    for btn in modal.find_elements(By.CSS_SELECTOR, "button"):
                        if "done" in btn.text.lower():
                            driver.execute_script("arguments[0].click();", btn)
                            break
                except Exception:
                    pass

                return "applied"

            elif "next" in btn_text or "review" in btn_text or "continue" in btn_text or "next" in aria:
                driver.execute_script("arguments[0].click();", primary_btn)
                _pause(1.0, 2.0)

                # Check for errors
                errors = modal.find_elements(By.CSS_SELECTOR, ".artdeco-inline-feedback__message")
                if errors:
                    visible_errors = [e.text for e in errors if e.is_displayed()]
                    if visible_errors:
                        print(f"    Validation errors: {visible_errors[:3]}")
                        # Try to fix and re-submit
                        _fill_form_fields(driver, modal)
                        _pause(0.5, 1.0)
                        driver.execute_script("arguments[0].click();", primary_btn)
                        _pause(1.0, 2.0)
            else:
                print(f"    Unknown button: '{btn_text}'")
                break

        # If we got here without submitting, dismiss the modal
        _dismiss_modal(driver)
        return "failed"

    except Exception as e:
        print(f"    Error: {e}")
        _dismiss_modal(driver)
        return "failed"


def _dismiss_modal(driver):
    """Close the Easy Apply modal and discard."""
    try:
        driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss']").click()
        _pause(0.5, 1.0)
    except Exception:
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            _pause(0.5, 1.0)
        except Exception:
            pass

    # Handle "Discard" confirmation
    try:
        for btn in driver.find_elements(By.CSS_SELECTOR, "button"):
            if "discard" in btn.text.lower():
                driver.execute_script("arguments[0].click();", btn)
                _pause(0.5, 1.0)
                break
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main search + apply loop
# ---------------------------------------------------------------------------

def run_linkedin_apply(limit: int = MAX_APPLICATIONS):
    applied = _load_applied()
    company_counts: dict[str, int] = {}
    for v in applied.values():
        if v.get("status") == "applied":
            c = v.get("company", "").lower()
            company_counts[c] = company_counts.get(c, 0) + 1

    driver = _make_driver()

    if not _wait_for_login(driver):
        driver.quit()
        return
    counts = {"applied": 0, "failed": 0, "skipped": 0}

    _telegram(f"LinkedIn Easy Apply bot starting. Target: {limit} applications.")

    try:
        for query in SEARCH_QUERIES:
            if counts["applied"] >= limit:
                break

            for loc_name, geo_id in SEARCH_LOCATIONS:
                if counts["applied"] >= limit:
                    break

                # Build search URL
                search_url = (
                    f"https://www.linkedin.com/jobs/search/?"
                    f"keywords={query.replace(' ', '+')}"
                    f"&location={loc_name.replace(' ', '+')}"
                    f"&geoId={geo_id}"
                    f"&f_AL=true"  # Easy Apply
                    f"&f_E=1"     # Job
                    f"&f_TPR=r2592000"  # Last month
                    f"&sortBy=DD"  # Newest first
                )

                print(f"\n  Searching: '{query}' in {loc_name}")
                try:
                    driver.current_url
                except Exception:
                    print("  Driver died — restarting Chrome...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = _make_driver()
                    if not _wait_for_login(driver):
                        return

                driver.get(search_url)
                _pause(2.0, 3.0)

                # Check if logged in
                if "/login" in driver.current_url:
                    print("  [ERROR] Not logged in! Close Chrome and log into LinkedIn first.")
                    return

                # Scroll through pages
                for page in range(4):  # 4 pages = ~100 jobs per query
                    if counts["applied"] >= limit:
                        break

                    _pause(1.0, 2.0)

                    # Get job cards
                    job_cards = driver.find_elements(By.CSS_SELECTOR,
                        "li.jobs-search-results__list-item, li[data-occludable-job-id]")

                    if not job_cards:
                        print(f"  No jobs found on page {page+1}")
                        break

                    print(f"  Page {page+1}: {len(job_cards)} jobs")

                    for card in job_cards:
                        if counts["applied"] >= limit:
                            break

                        try:
                            # Scroll card into view
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                            _pause(0.5, 1.0)

                            # Get job info
                            job_id = card.get_attribute("data-occludable-job-id") or ""
                            job_id = job_id.split(":")[-1] if job_id else ""

                            title = ""
                            company = ""
                            try:
                                title_el = card.find_element(By.CSS_SELECTOR, ".job-card-list__title, .artdeco-entity-lockup__title")
                                title = title_el.text.strip()
                            except Exception:
                                pass
                            try:
                                comp_el = card.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle, .job-card-container__primary-description")
                                company = comp_el.text.strip()
                            except Exception:
                                pass

                            # Skip if not intern
                            if "intern" not in title.lower():
                                continue

                            # Skip if already applied
                            if job_id and job_id in applied:
                                continue

                            # Check "Applied" badge
                            try:
                                footer = card.find_element(By.CSS_SELECTOR, ".job-card-container__footer-job-state")
                                if "applied" in footer.text.lower():
                                    continue
                            except Exception:
                                pass

                            # Per-company limit
                            if company_counts.get(company.lower(), 0) >= MAX_PER_COMPANY:
                                continue

                            print(f"\n  [{counts['applied']+1}] {company} — {title[:50]}")

                            status = _apply_to_job(driver, card, job_id)
                            counts[status] += 1

                            if job_id:
                                applied[job_id] = {
                                    "title": title,
                                    "company": company,
                                    "status": status,
                                    "applied_at": datetime.now().isoformat(),
                                }
                                _save_applied(applied)

                            if status == "applied":
                                company_counts[company.lower()] = company_counts.get(company.lower(), 0) + 1
                                print(f"    [APPLIED] ✓")
                            elif status == "failed":
                                print(f"    [FAILED]")
                            else:
                                print(f"    [SKIPPED]")

                            if counts["applied"] > 0 and counts["applied"] % 25 == 0:
                                _telegram(
                                    f"LinkedIn progress: <b>{counts['applied']}</b> applied, "
                                    f"{counts['failed']} failed, {counts['skipped']} skipped."
                                )

                            _pause(1.5, 3.0)

                        except StaleElementReferenceException:
                            continue

                    # Next page
                    try:
                        next_btn = driver.find_element(By.CSS_SELECTOR, f"button[aria-label='Page {page+2}']")
                        driver.execute_script("arguments[0].click();", next_btn)
                        _pause(2.0, 4.0)
                    except Exception:
                        break  # no more pages

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        _save_applied(applied)

        summary = (
            f"LinkedIn Easy Apply complete.\n"
            f"Applied: <b>{counts['applied']}</b>\n"
            f"Failed: {counts['failed']}\n"
            f"Skipped: {counts['skipped']}"
        )
        print(f"\n{summary}")
        _telegram(summary)


if __name__ == "__main__":
    run_linkedin_apply()
