"""
Hands-free Selenium applier for Greenhouse and Lever job applications.
Fills forms automatically, uploads resume, submits, logs results.
Run this overnight — it will Telegram you when done.
"""

from __future__ import annotations
import json
import os
import random
import time
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROFILE = {
    "first_name": "Amanuel",
    "last_name": "Abu",
    "full_name": "Amanuel Abu",
    "email": os.getenv("EMAIL", "amanuelalexabu@gmail.com"),
    "phone": os.getenv("PHONE", "(669) 292-8473"),
    "linkedin": os.getenv("LINKEDIN", "https://www.linkedin.com/in/amanuelabu"),
    "github": "https://github.com/amanuel2x",
    "location": os.getenv("LOCATION", "San Francisco, CA"),
    "university": "San Francisco State University",
    "degree": "Bachelor of Science",
    "major": "Computer Science",
    "gpa": "",
    "grad_year": "2026",
    "resume_path": str(Path(__file__).parent / "Amanuel_Abu_Resume.pdf"),
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APPLIED_LOG = Path(__file__).parent / "applied.json"
MATCHES_FILE = Path(__file__).parent / "matches.json"

APPLY_LIMIT = int(os.getenv("APPLY_LIMIT_PER_RUN", "200"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pause(lo=0.8, hi=2.2):
    time.sleep(random.uniform(lo, hi))


def _type(element, text: str):
    """Type text character by character with human-like delays."""
    element.clear()
    for char in str(text):
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.13))


def _fill_by_id(driver, field_id: str, value: str):
    """Fill a text input by its ID. Clicks via JS to avoid intercept errors."""
    try:
        el = driver.find_element(By.ID, field_id)
        if not el.is_displayed():
            return False
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        _pause(0.2, 0.4)
        driver.execute_script("arguments[0].click();", el)
        _pause(0.1, 0.2)
        el.clear()
        for ch in str(value):
            el.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.08))
        _pause(0.2, 0.4)
        return True
    except Exception:
        return False


def _fill_react_dropdown(driver, field_id: str, search_text: str):
    """Fill a React custom dropdown (rendered as text input with autocomplete).
    Types search text, waits for dropdown options, selects first match."""
    from selenium.webdriver.common.keys import Keys
    try:
        el = driver.find_element(By.ID, field_id)
        if not el.is_displayed():
            return False
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        _pause(0.2, 0.4)
        driver.execute_script("arguments[0].click();", el)
        _pause(0.2, 0.3)
        el.clear()
        for ch in str(search_text):
            el.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.08))
        _pause(0.5, 1.0)  # wait for autocomplete dropdown to appear
        el.send_keys(Keys.RETURN)  # select first option
        _pause(0.3, 0.5)
        # Click body to dismiss any lingering dropdown
        driver.execute_script("document.body.click();")
        _pause(0.1, 0.2)
        return True
    except Exception:
        return False


def _safe_find(driver, by, selector, timeout=6):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None


def _safe_click(driver, by, selector, timeout=6):
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        _pause(0.3, 0.7)
        el.click()
        return True
    except Exception:
        return False


def _fill_if_exists(driver, selector, value, by=By.CSS_SELECTOR):
    el = _safe_find(driver, by, selector, timeout=4)
    if el and el.is_displayed() and el.is_enabled():
        try:
            _type(el, value)
            return True
        except ElementNotInteractableException:
            pass
    return False


def _select_if_exists(driver, selector, value_contains: str, by=By.CSS_SELECTOR):
    el = _safe_find(driver, by, selector, timeout=4)
    if el:
        try:
            sel = Select(el)
            for option in sel.options:
                if value_contains.lower() in option.text.lower():
                    sel.select_by_visible_text(option.text)
                    return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Claude — reads the whole form and answers everything in one shot
# ---------------------------------------------------------------------------

# Fields we fill explicitly — skip in the AI scan
_HANDLED_IDS = {
    "first_name", "last_name", "email", "phone", "candidate-location",
    "school--0", "degree--0", "discipline--0", "end-year--0", "preferred_name",
}

_APPLICANT_CONTEXT = """
You are filling out a job application for Amanuel Abu. Here is his info:
- Full name: Amanuel Abu
- Email: amanuelalexabu@gmail.com
- Phone: (669) 292-8473
- Location: San Francisco, CA 94132
- University: San Francisco State University (SFSU)
- Degree: Bachelor of Science in Computer Science
- GPA: 3.5
- Graduation: May 2026
- LinkedIn: https://www.linkedin.com/in/amanuelabu
- GitHub / Website / Portfolio: https://github.com/amanuel2x
- Gender: Male
- Race/Ethnicity: Black or African American
- Hispanic/Latino: No
- Sexual Orientation: Straight / Heterosexual
- Pronouns: He/Him
- Disability: No
- Veteran: No, not a protected veteran
- Work authorization: Yes, authorized to work in the US
- Visa sponsorship needed: No
- Available start date: June 2026
- Willing to relocate: Yes
- Open to remote: Yes
- Years of experience: 1 (internships + projects)
- How did you hear about us: Company website

Rules:
- For disability questions: answer "No" (short, will match any "No" option in dropdown).
- For veteran questions: answer "No" or "I am not a protected veteran".
- For gender/gender identity: answer "Male".
- For race/ethnicity questions: answer "Black".
- For Hispanic/Latino: answer "No".
- For sexual orientation: answer "Heterosexual".
- For pronouns: answer "He/Him".
- For work authorization: answer "Yes".
- For sponsorship: answer "No".
- NEVER choose "Decline" or "I don't wish to answer" — always give a real answer.
- Keep dropdown answers SHORT (1-3 words) so they match the autocomplete filter. For example answer "No" not "No, I do not have a disability and have not had one in the past".
- For cover letter fields: write 2-3 sentences about being excited to apply and how skills in Python, React, and systems programming align with the role.
- For salary: "Open to discussion" or the lowest reasonable option if forced.
- ALWAYS pick a valid option — never leave a required field blank.
- If a select has options, your answer MUST exactly match one of them (case-insensitive substring match is fine).
""".strip()


def _get_label_for(driver, el) -> str:
    """Find the label text for a form element."""
    el_id = el.get_attribute("id") or ""
    if el_id:
        try:
            lbl = driver.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
            return lbl.text.strip()
        except Exception:
            pass
    aria = el.get_attribute("aria-label") or ""
    if aria:
        return aria.strip()
    placeholder = el.get_attribute("placeholder") or ""
    if placeholder:
        return placeholder.strip()
    try:
        return el.find_element(By.XPATH, "ancestor::label[1]").text.strip()
    except Exception:
        pass
    try:
        return el.find_element(By.XPATH, "preceding-sibling::label[1]").text.strip()
    except Exception:
        pass
    return el.get_attribute("name") or ""


def _scan_form_fields(driver) -> list[dict]:
    """
    Walk the page and collect every unfilled/unanswered visible field.
    Returns a list of dicts: {id, type, label, options, element}
    """
    fields = []
    seen_ids = set()

    def _add(fid, ftype, label, options, el):
        key = fid or label
        if key and key not in seen_ids and label:
            seen_ids.add(key)
            fields.append({"id": fid, "type": ftype, "label": label, "options": options, "element": el})

    # Text / textarea inputs
    for inp in driver.find_elements(By.CSS_SELECTOR, "input, textarea"):
        try:
            if not inp.is_displayed() or not inp.is_enabled():
                continue
            itype = inp.get_attribute("type") or "text"
            if itype in ("file", "hidden", "submit", "button", "checkbox", "radio"):
                continue
            fid = inp.get_attribute("id") or ""
            if any(skip in fid for skip in _HANDLED_IDS):
                continue
            val = inp.get_attribute("value") or ""
            if val.strip():
                continue
            label = _get_label_for(driver, inp)
            if label:
                _add(fid, "textarea" if inp.tag_name == "textarea" else "text", label, [], inp)
        except Exception:
            continue

    # Selects
    for sel_el in driver.find_elements(By.TAG_NAME, "select"):
        try:
            if not sel_el.is_displayed():
                continue
            fid = sel_el.get_attribute("id") or ""
            if any(skip in fid for skip in _HANDLED_IDS):
                continue
            s = Select(sel_el)
            cur = s.first_selected_option.get_attribute("value") or ""
            if cur not in ("", "0", "select", "none", "__default__"):
                continue  # already answered
            label = _get_label_for(driver, sel_el)
            opts = [o.text.strip() for o in s.options if o.text.strip() and o.get_attribute("value")]
            if label:
                _add(fid, "select", label, opts, sel_el)
        except Exception:
            continue

    # Checkbox groups (e.g. "select all that apply" compliance questions)
    checkbox_groups: dict[str, list] = {}
    for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        try:
            if not cb.is_displayed():
                continue
            if cb.is_selected():
                continue
            name = cb.get_attribute("name") or cb.get_attribute("id") or ""
            # Group by shared parent container (fieldset or div class)
            try:
                parent = cb.find_element(By.XPATH, "ancestor::fieldset[1]")
                group_key = parent.get_attribute("id") or parent.get_attribute("class") or name
            except Exception:
                group_key = name
            checkbox_groups.setdefault(group_key, []).append(cb)
        except Exception:
            continue

    for group_key, checkboxes in checkbox_groups.items():
        try:
            # Get group label from fieldset legend or first checkbox's ancestor
            group_label = ""
            try:
                parent = checkboxes[0].find_element(By.XPATH, "ancestor::fieldset[1]")
                try:
                    group_label = parent.find_element(By.TAG_NAME, "legend").text.strip()
                except Exception:
                    pass
            except Exception:
                pass
            opts = []
            for cb in checkboxes:
                lbl = _get_label_for(driver, cb)
                if lbl:
                    opts.append(lbl)
            if group_label and opts:
                _add(group_key, "checkbox_group", group_label, opts, checkboxes[0])
        except Exception:
            continue

    # Radio groups
    radio_groups: dict[str, list] = {}
    for r in driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
        try:
            name = r.get_attribute("name") or ""
            if name:
                radio_groups.setdefault(name, []).append(r)
        except Exception:
            continue

    for name, radios in radio_groups.items():
        try:
            if any(r.is_selected() for r in radios):
                continue
            label = _get_label_for(driver, radios[0]) or name.replace("_", " ")
            opts = []
            for r in radios:
                lbl = r.get_attribute("aria-label") or r.get_attribute("value") or ""
                # try sibling label text
                try:
                    lbl = r.find_element(By.XPATH, "following-sibling::label[1]").text.strip() or lbl
                except Exception:
                    pass
                if lbl:
                    opts.append(lbl)
            _add(name, "radio", label, opts, radios[0])
        except Exception:
            continue

    return fields


def _claude_answer_all(fields: list[dict], job_title: str = "", company: str = "") -> dict[str, str]:
    """
    Send ALL form fields to Claude in one call.
    Returns {field_id_or_label: answer_string}
    """
    if not fields:
        return {}

    if not _HAS_ANTHROPIC or not ANTHROPIC_API_KEY:
        return {}

    # Build a structured question list
    lines = []
    for i, f in enumerate(fields):
        opts = f" [options: {' | '.join(f['options'])}]" if f["options"] else ""
        lines.append(f"{i+1}. [{f['type'].upper()}] {f['label']}{opts}")

    prompt = (
        f"{_APPLICANT_CONTEXT}\n\n"
        f"Job: {job_title} at {company}\n\n"
        f"Fill out these form fields. Reply with a JSON object mapping field number (as string) to the answer.\n"
        f"For CHECKBOX_GROUP fields, return a comma-separated list of the option(s) to check (e.g. 'None of the above').\n"
        f"Example: {{\"1\": \"United States\", \"2\": \"Decline to self-identify\", \"3\": \"None of the above\"}}\n\n"
        f"Fields:\n" + "\n".join(lines)
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Extract JSON from the response
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            answers = json.loads(m.group())
            # Map back to field label/id
            result = {}
            for k, v in answers.items():
                idx = int(k) - 1
                if 0 <= idx < len(fields):
                    f = fields[idx]
                    result[f["id"] or f["label"]] = str(v)
            return result
    except Exception as e:
        print(f"  [CLAUDE] Error: {e}")

    return {}


def _apply_answers(driver, fields: list[dict], answers: dict[str, str]):
    """Fill form fields using the answers Claude returned."""
    for f in fields:
        key = f["id"] or f["label"]
        answer = answers.get(key, "")
        if not answer:
            continue
        el = f["element"]
        ftype = f["type"]
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            _pause(0.1, 0.3)
            if ftype == "select":
                sel = Select(el)
                matched = False
                for opt in sel.options:
                    if answer.lower() in opt.text.lower() or opt.text.lower() in answer.lower():
                        sel.select_by_visible_text(opt.text)
                        matched = True
                        break
                if not matched and f["options"]:
                    sel.select_by_visible_text(f["options"][0])
            elif ftype == "radio":
                # Click the radio whose label matches
                name = f["id"]  # for radio, id = group name
                for r in driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']"):
                    lbl = r.get_attribute("aria-label") or r.get_attribute("value") or ""
                    try:
                        lbl = r.find_element(By.XPATH, "following-sibling::label[1]").text.strip() or lbl
                    except Exception:
                        pass
                    if answer.lower() in lbl.lower() or lbl.lower() in answer.lower():
                        driver.execute_script("arguments[0].click();", r)
                        break
                else:
                    radios = driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']")
                    if radios:
                        driver.execute_script("arguments[0].click();", radios[0])
            elif ftype == "checkbox_group":
                # Claude returns comma-separated list of options to check
                chosen = [c.strip().lower() for c in answer.split(",")]
                for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                    if not cb.is_displayed():
                        continue
                    lbl = _get_label_for(driver, cb)
                    if any(c in lbl.lower() for c in chosen):
                        if not cb.is_selected():
                            driver.execute_script("arguments[0].click();", cb)
                            _pause(0.1, 0.2)
            else:
                # React forms: text inputs are often dropdowns in disguise
                # Use _fill_react_dropdown if we have an ID, otherwise type+Enter
                fid = f.get("id", "")
                if fid:
                    _fill_react_dropdown(driver, fid, answer)
                else:
                    from selenium.webdriver.common.keys import Keys
                    driver.execute_script("arguments[0].click();", el)
                    _pause(0.1, 0.2)
                    el.clear()
                    for ch in str(answer):
                        el.send_keys(ch)
                        time.sleep(random.uniform(0.03, 0.08))
                    _pause(0.5, 0.8)
                    el.send_keys(Keys.RETURN)
                    _pause(0.2, 0.3)
                driver.execute_script("document.body.click();")
            _pause(0.2, 0.5)
        except Exception as e:
            print(f"  [FILL] Could not fill '{f['label']}': {e}")


def _handle_extra_questions(driver, job_title: str = "", company: str = ""):
    """Scan every unfilled field, send them all to Claude, fill with answers."""
    _pause(0.5, 1.0)
    fields = _scan_form_fields(driver)
    if not fields:
        return
    print(f"  [CLAUDE] Scanning {len(fields)} unfilled fields...")
    for f in fields:
        opts = f" [{' | '.join(f['options'][:4])}]" if f["options"] else ""
        print(f"    - {f['label']}{opts}")
    answers = _claude_answer_all(fields, job_title, company)
    print(f"  [CLAUDE] Got {len(answers)} answers")
    _apply_answers(driver, fields, answers)


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


def _already_applied(job_id: str, applied: dict) -> bool:
    return applied.get(job_id, {}).get("status") == "applied"


def _log_applied(job: dict, status: str, applied: dict):
    applied[job["id"]] = {
        "id": job["id"],
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "url": job.get("url", ""),
        "status": status,
        "applied_at": datetime.now().isoformat(),
        "match_score": job.get("match_score", 0),
        "is_bay_area": job.get("is_bay_area", False),
        "is_remote": job.get("is_remote", False),
        "has_housing": job.get("has_housing", False),
    }


# ---------------------------------------------------------------------------
# Greenhouse form filler
# ---------------------------------------------------------------------------

def _dismiss_popups(driver):
    """Dismiss cookie banners, modals, location prompts before filling forms."""
    # Accept/dismiss browser-level dialogs
    try:
        driver.switch_to.alert.dismiss()
    except Exception:
        pass

    # Common cookie/consent/modal buttons to click
    dismiss_selectors = [
        # Cookie banners
        "button[id*='accept']", "button[class*='accept']",
        "button[id*='cookie']", "button[class*='cookie']",
        "button[aria-label*='Accept']", "button[aria-label*='accept']",
        "[data-testid*='cookie'] button", "[id*='gdpr'] button",
        # Close/dismiss modals
        "button[aria-label='Close']", "button[aria-label='close']",
        "button[class*='close']", "button[class*='dismiss']",
        "button[id*='close']", "[class*='modal'] button[class*='close']",
        # "No thanks" / decline style
        "button[class*='decline']", "button[class*='reject']",
    ]

    for sel in dismiss_selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].click();", el)
                    _pause(0.3, 0.6)
                    break
        except Exception:
            continue

    # Dismiss by text content
    dismiss_texts = ["accept all", "accept cookies", "i agree", "got it", "ok", "close", "no thanks", "dismiss"]
    try:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            if btn.text.strip().lower() in dismiss_texts and btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                _pause(0.3, 0.6)
                break
    except Exception:
        pass


def _fetch_greenhouse_questions(board_token: str, job_id: str) -> tuple[list[dict], list[dict]]:
    """Fetch questions and compliance fields from Greenhouse API for a job."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true"
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        if r.status_code != 200:
            return [], []
        data = r.json()
        return data.get("questions") or [], data.get("compliance") or []
    except Exception as e:
        print(f"  [API] Failed to fetch questions: {e}")
        return [], []


def _greenhouse_board_token(url: str) -> str:
    """Extract board token from a Greenhouse URL."""
    import re
    # https://job-boards.greenhouse.io/verkada/jobs/123
    # https://boards.greenhouse.io/verkada/jobs/123
    m = re.search(r'greenhouse\.io/([^/]+)/jobs/', url)
    return m.group(1) if m else ""


def _greenhouse_job_id(url: str) -> str:
    """Extract job ID from a Greenhouse URL."""
    import re
    m = re.search(r'/jobs/(\d+)', url)
    return m.group(1) if m else ""


# Known answers for standard fields — Claude handles the rest
_STANDARD_FIELDS = {
    "first_name": lambda p: p["first_name"],
    "last_name": lambda p: p["last_name"],
    "email": lambda p: p["email"],
    "phone": lambda p: p["phone"],
    "preferred_name": lambda p: p["first_name"],
    "candidate_location": lambda p: p["location"],
}


def _build_claude_questions(questions: list[dict], compliance: list[dict]) -> list[dict]:
    """Build a list of questions that need Claude's help (not standard fields)."""
    to_ask = []
    for q in questions:
        for f in q.get("fields", []):
            fname = f["name"]
            ftype = f["type"]
            # Skip standard fields we handle directly
            if fname in _STANDARD_FIELDS or fname in ("resume", "resume_text", "cover_letter", "cover_letter_text"):
                continue
            # Skip file-only fields (transcript uploads etc)
            if ftype == "input_file":
                continue
            opts = []
            for v in f.get("values", []):
                opts.append({"label": v["label"], "value": v["value"]})
            to_ask.append({
                "name": fname,
                "label": q.get("label", fname),
                "type": ftype,
                "required": q.get("required", False),
                "options": opts,
            })

    # Add EEOC/compliance questions
    for section in compliance:
        for q in section.get("questions", []):
            label = q.get("label", "")
            for f in q.get("fields", []):
                fname = f["name"]
                ftype = f["type"]
                opts = [{"label": v["label"], "value": v["value"]} for v in f.get("values", [])]
                to_ask.append({
                    "name": fname,
                    "label": label,
                    "type": ftype,
                    "required": q.get("required", False),
                    "options": opts,
                })

    return to_ask


def _claude_answer_greenhouse(to_ask: list[dict], job_title: str, company: str) -> dict[str, str]:
    """Send all Greenhouse questions to Claude, get answers back."""
    if not to_ask or not _HAS_ANTHROPIC or not ANTHROPIC_API_KEY:
        return {}

    lines = []
    for i, q in enumerate(to_ask):
        opts_str = ""
        if q["options"]:
            opts_str = " OPTIONS: " + " | ".join(
                f"\"{o['label']}\" (value={o['value']})" for o in q["options"]
            )
        req = " [REQUIRED]" if q["required"] else ""
        lines.append(f"{i+1}. [{q['type']}] {q['label']}{req}{opts_str}")

    prompt = (
        f"{_APPLICANT_CONTEXT}\n\n"
        f"Job: {job_title} at {company}\n\n"
        f"Answer each form field below. Reply with a JSON object mapping field number (as string) to the answer.\n"
        f"For SELECT fields with OPTIONS: return the EXACT option label text (not the numeric value). "
        f"Pick the best matching option.\n"
        f"For text fields: return the text answer.\n"
        f"Example: {{\"1\": \"Sept - Dec 2026\", \"2\": \"https://linkedin.com/in/example\", \"3\": \"I don't wish to answer\"}}\n\n"
        f"Fields:\n" + "\n".join(lines)
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            answers = json.loads(m.group())
            result = {}
            for k, v in answers.items():
                idx = int(k) - 1
                if 0 <= idx < len(to_ask):
                    result[to_ask[idx]["name"]] = str(v)
            return result
    except Exception as e:
        print(f"  [CLAUDE] Error: {e}")
    return {}


def _fill_greenhouse(driver, job: dict) -> bool:
    """Fill a Greenhouse React form — API for questions, Claude for answers, Selenium to fill."""
    p = PROFILE
    url = job.get("apply_url") or job.get("url", "")
    board_token = _greenhouse_board_token(url)
    job_id = _greenhouse_job_id(url)

    try:
        # Step 1: Fetch exact questions from Greenhouse API (before touching the form)
        questions, compliance = [], []
        api_question_map = {}  # field_name -> {label, type, options, required}
        if board_token and job_id:
            questions, compliance = _fetch_greenhouse_questions(board_token, job_id)
            if questions:
                print(f"  [API] Got {len(questions)} questions + {len(compliance)} compliance")

        # Step 2: Get Claude's answers for all non-standard questions
        to_ask = _build_claude_questions(questions, compliance)
        answers = {}
        if to_ask:
            print(f"  [CLAUDE] Asking about {len(to_ask)} fields...")
            answers = _claude_answer_greenhouse(to_ask, job.get("title", ""), job.get("company", ""))
            print(f"  [CLAUDE] Got {len(answers)} answers")
            # Build lookup: field_name -> {type, options} for filling strategy
            for q in to_ask:
                api_question_map[q["name"]] = q

        # Step 3: Fill standard text fields by ID
        _fill_by_id(driver, "first_name", p["first_name"])
        _fill_by_id(driver, "last_name", p["last_name"])
        _fill_by_id(driver, "preferred_name", p["first_name"])
        _fill_by_id(driver, "email", p["email"])
        _fill_by_id(driver, "phone", p["phone"])

        # Country is a React dropdown
        _fill_react_dropdown(driver, "country", "United States")

        # Location is a text field with autocomplete
        _fill_by_id(driver, "candidate-location", p["location"])
        # Dismiss autocomplete
        from selenium.webdriver.common.keys import Keys
        try:
            loc_el = driver.find_element(By.ID, "candidate-location")
            _pause(0.5, 1.0)
            loc_el.send_keys(Keys.ESCAPE)
            _pause(0.2, 0.3)
        except Exception:
            pass

        # Resume upload
        try:
            resume_el = driver.find_element(By.ID, "resume")
            resume_el.send_keys(p["resume_path"])
            _pause(1.5, 2.5)
            print(f"  Uploaded resume")
        except Exception:
            pass

        # Education — all React dropdowns with autocomplete
        _fill_react_dropdown(driver, "school--0", "San Francisco State")
        _fill_react_dropdown(driver, "degree--0", "Bachelor")
        _fill_react_dropdown(driver, "discipline--0", "Computer Science")
        _fill_by_id(driver, "end-year--0", p["grad_year"])

        # Step 4: Fill Claude's answers — EVERY field gets tried, never stop
        def _fill_answer(field_name, answer):
            """Try to fill a single field. Returns True if filled."""
            q_info = api_question_map.get(field_name, {})
            q_type = q_info.get("type", "input_text")
            try:
                if q_type == "multi_value_multi_select":
                    # Checkboxes — find by label text and click
                    filled = False
                    choices = [c.strip().lower() for c in answer.split(",")]
                    for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                        try:
                            if not cb.is_displayed():
                                continue
                            lbl = _get_label_for(driver, cb)
                            if any(c in lbl.lower() for c in choices):
                                if not cb.is_selected():
                                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cb)
                                    _pause(0.1, 0.2)
                                    driver.execute_script("arguments[0].click();", cb)
                                    filled = True
                                    _pause(0.2, 0.4)
                        except Exception:
                            continue
                    if not filled:
                        # Fallback: try as dropdown
                        filled = _fill_react_dropdown(driver, field_name.rstrip("[]"), answer)
                elif q_type == "multi_value_single_select":
                    filled = _fill_react_dropdown(driver, field_name, answer)
                elif q_type in ("input_text", "textarea"):
                    filled = _fill_by_id(driver, field_name, answer)
                else:
                    filled = _fill_react_dropdown(driver, field_name, answer)
                    if not filled:
                        filled = _fill_by_id(driver, field_name, answer)
                if filled:
                    print(f"  Filled #{field_name} = {answer[:40]}")
                else:
                    print(f"  [MISS] #{field_name} — not on page yet, continuing...")
                return filled
            except Exception as e:
                print(f"  [SKIP] #{field_name} — {e}")
                return False

        for field_name, answer in answers.items():
            _fill_answer(field_name, answer)

        # Step 5: Conditional field loop — dropdowns reveal new fields.
        # Keep scanning for unfilled fields until no new ones appear.
        for scan_pass in range(4):
            _pause(0.5, 1.0)
            # Get all currently visible empty fields
            visible_ids = set()
            for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], textarea, select"):
                try:
                    if not inp.is_displayed():
                        continue
                    fid = inp.get_attribute("id") or ""
                    if not fid or fid in _HANDLED_IDS:
                        continue
                    val = inp.get_attribute("value") or ""
                    if not val.strip():
                        visible_ids.add(fid)
                except Exception:
                    continue

            if not visible_ids:
                break

            # Try filling from existing Claude answers first
            newly_filled = 0
            for fid in list(visible_ids):
                if fid in answers:
                    if _fill_answer(fid, answers[fid]):
                        newly_filled += 1
                        visible_ids.discard(fid)

            # For remaining unknown fields, ask Claude
            if visible_ids:
                print(f"  [SCAN {scan_pass+1}] Found {len(visible_ids)} new unfilled fields: {visible_ids}")
                _handle_extra_questions(driver, job.get("title", ""), job.get("company", ""))
                newly_filled += 1  # assume handle_extra got some

            if newly_filled == 0:
                break  # nothing new to fill

        # Step 6: Scroll down and submit — try up to 2 times
        for attempt in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            _pause(1.0, 2.0)

            submitted = False
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                txt = btn.text.strip().lower()
                if txt in ("submit application", "submit"):
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    _pause(0.3, 0.6)
                    driver.execute_script("arguments[0].click();", btn)
                    submitted = True
                    print(f"  Clicked: '{btn.text.strip()}' (attempt {attempt+1})")
                    break

            if not submitted:
                print(f"  [ERROR] No submit button found")
                return False

            _pause(3.0, 5.0)

            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                if "thank" in page_text or "confirm" in page_text or "submitted" in page_text or "received" in page_text:
                    print(f"  [CONFIRMED] Application submitted!")
                    return True
            except Exception:
                return True  # page changed, probably submitted

            # If still on form and first attempt, try to fix errors and resubmit
            if attempt == 0:
                print(f"  [RETRY] Still on form — trying to fix remaining fields...")
                # Look for error messages near required fields
                errors = driver.find_elements(By.CSS_SELECTOR, "[class*='error'], [class*='invalid']")
                for err in errors[:5]:
                    try:
                        if err.is_displayed():
                            print(f"    Error: {err.text.strip()[:60]}")
                    except Exception:
                        pass
                # Try filling any remaining empty required fields
                _handle_extra_questions(driver, job.get("title", ""), job.get("company", ""))

        return True  # submitted at least once, count it

    except Exception as e:
        import traceback
        print(f"  Greenhouse fill error: {e}")
        print(f"  {traceback.format_exc().splitlines()[-1]}")

    return False


# ---------------------------------------------------------------------------
# Lever form filler
# ---------------------------------------------------------------------------

def _fill_lever(driver, job: dict) -> bool:
    """Fill a Lever application form. Returns True if submitted."""
    p = PROFILE

    try:
        # If we're on the job description page, click Apply to get to the form
        current = driver.current_url.lower()
        if "jobs.lever.co" in current and "/apply" not in current:
            _dismiss_popups(driver)
            clicked = _safe_click(driver, By.CSS_SELECTOR,
                "a.postings-btn[href*='/apply'], a[href*='/apply'], button[data-qa='btn-apply']")
            if clicked:
                _pause(2.0, 3.5)
            else:
                for el in driver.find_elements(By.TAG_NAME, "a"):
                    if el.text.strip().lower() in ("apply", "apply now", "apply for this job"):
                        el.click()
                        _pause(2.0, 3.5)
                        break
            _dismiss_popups(driver)

        _fill_if_exists(driver, "input#name, input[name='name']", p["full_name"])
        _pause(0.3, 0.8)

        _fill_if_exists(driver, "input#email, input[name='email']", p["email"])
        _pause(0.3, 0.8)

        _fill_if_exists(driver, "input#phone, input[name='phone']", p["phone"])
        _pause(0.3, 0.8)

        # LinkedIn / URLs
        for sel in ["input[name='urls[LinkedIn]']", "input[placeholder*='LinkedIn']"]:
            if _fill_if_exists(driver, sel, p["linkedin"]):
                break

        for sel in ["input[name='urls[GitHub]']", "input[placeholder*='GitHub']"]:
            if _fill_if_exists(driver, sel, p["github"]):
                break

        # Resume upload
        resume_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        for inp in resume_inputs:
            try:
                inp.send_keys(p["resume_path"])
                _pause(1.5, 3.0)
                break
            except Exception:
                continue

        # Location
        _fill_if_exists(driver, "input[name='location'], input[placeholder*='location']", p["location"])
        _pause(0.3, 0.6)

        # Handle unexpected/extra questions with Claude
        _handle_extra_questions(driver, job.get("title", ""), job.get("company", ""))

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        _pause(1.0, 2.0)

        submitted = _safe_click(driver, By.CSS_SELECTOR,
            "button[type='submit'], input[type='submit']")

        if not submitted:
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                if "submit" in btn.text.lower() or "apply" in btn.text.lower():
                    btn.click()
                    submitted = True
                    break

        if submitted:
            _pause(2.0, 4.0)
            return True

    except Exception as e:
        print(f"  Lever fill error: {e}")

    return False


# ---------------------------------------------------------------------------
# Main apply loop
# ---------------------------------------------------------------------------

def _make_driver():
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.178 Safari/537.36"
    )
    import glob
    wdm_path = ChromeDriverManager().install()
    # wdm sometimes returns the wrong file — find the actual binary
    driver_dir = str(Path(wdm_path).parent)
    candidates = glob.glob(f"{driver_dir}/chromedriver*")
    binary = next((p for p in candidates if not p.endswith(".chromedriver") and "NOTICE" not in p and Path(p).is_file()), wdm_path)
    service = Service(binary)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(25)
    driver.implicitly_wait(3)
    return driver


# Companies with custom portals that can't be auto-filled
SKIP_COMPANIES = {
    "google", "alphabet", "microsoft", "apple", "meta", "amazon",
    "adobe", "notion", "salesforce", "oracle", "ibm",
    "boeing", "raytheon", "qualcomm", "nvidia", "intel",
}

SKIP_DOMAINS = {
    "figma.com", "notion.so", "ashbyhq.com", "adobe.com",
    "myworkdayjobs.com", "taleo.net", "icims.com", "successfactors.com",
    "jobvite.com", "smartrecruiters.com", "workable.com",
    "careers.google.com", "google.com/about/careers", "google.com",
    "amazon.jobs", "microsoft.com", "meta.com", "apple.com",
    "accounts.google.com", "linkedin.com",
}


def _is_skippable(url: str) -> bool:
    return any(d in url.lower() for d in SKIP_DOMAINS)


def apply_to_job(driver, job: dict) -> str:
    """Returns: 'applied', 'skipped', 'failed'"""
    url = job.get("apply_url") or job.get("url", "")
    source = job.get("source", "")
    title = job.get("title", "")
    company = job.get("company", "")

    if not url:
        return "skipped"

    if _is_skippable(url):
        print(f"  Skipping custom portal: {company}")
        return "skipped"

    if any(s in company.lower() for s in SKIP_COMPANIES):
        print(f"  Skipping known custom portal company: {company}")
        return "skipped"

    print(f"\n  Applying: {company} — {title}")
    print(f"  URL: {url}")

    try:
        driver.set_page_load_timeout(20)

        driver.get(url)
        _pause(2.0, 3.5)

        # Click the Apply button — may open form inline or in a new tab
        if "greenhouse.io" in url.lower():
            original_window = driver.current_window_handle
            original_handles = set(driver.window_handles)

            for btn in driver.find_elements(By.TAG_NAME, "button"):
                if btn.text.strip().lower() == "apply" and btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    break
            _pause(2.0, 3.0)

            # If a new tab opened, switch to it
            new_handles = set(driver.window_handles) - original_handles
            if new_handles:
                driver.switch_to.window(new_handles.pop())
                print(f"  Switched to new tab: {driver.current_url[:60]}")
                _pause(1.5, 2.5)

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            _pause(1.0, 1.5)

        current = driver.current_url.lower()

        if _is_skippable(current) or "accounts.google.com" in current:
            print(f"  [SKIP] Redirected to login/custom portal: {current[:60]}")
            driver.get("about:blank")
            return "skipped"

        _dismiss_popups(driver)
        _pause(0.5, 1.0)

        if "greenhouse.io" in current:
            print(f"  [GREENHOUSE] Filling form...")
            success = _fill_greenhouse(driver, job)
        elif "lever.co" in current:
            print(f"  [LEVER] Filling form...")
            success = _fill_lever(driver, job)
        else:
            print(f"  [UNKNOWN] Trying generic fill on: {current[:60]}")
            success = _fill_greenhouse(driver, job)
            if not success:
                success = _fill_lever(driver, job)

        status = "applied" if success else "failed"
        print(f"  [RESULT] {status.upper()}")
        return status

    except Exception as e:
        import traceback
        print(f"  [ERROR] {company} — {type(e).__name__}: {e}")
        print(f"  [TRACE] {traceback.format_exc().splitlines()[-1]}")
        return "failed"


def run_auto_apply(limit: int = APPLY_LIMIT):
    if not MATCHES_FILE.exists():
        print("No matches.json found. Run main.py --scrape-only first.")
        return

    jobs = json.loads(MATCHES_FILE.read_text())
    applied = _load_applied()

    # Only use direct Greenhouse/Lever jobs — SimplifyJobs URLs too often hit Workday/custom portals
    def _is_direct_ats(job):
        """Only accept jobs whose URL goes directly to greenhouse.io or lever.co."""
        url = (job.get("apply_url") or job.get("url", "")).lower()
        return "greenhouse.io/" in url or "lever.co/" in url

    MAX_PER_COMPANY = 3

    # Count how many we've already applied to per company
    company_counts: dict[str, int] = {}
    for entry in applied.values():
        if entry.get("status") == "applied":
            c = entry.get("company", "").lower()
            company_counts[c] = company_counts.get(c, 0) + 1

    def _is_intern_role(job):
        """Only apply to internship roles."""
        title = job.get("title", "").lower()
        return "intern" in title

    eligible = [
        j for j in jobs
        if j.get("source") in ("Greenhouse", "Lever")
        and _is_direct_ats(j)
        and _is_intern_role(j)
        and not _already_applied(j["id"], applied)
        and company_counts.get(j.get("company", "").lower(), 0) < MAX_PER_COMPANY
    ]

    print(f"\nEligible for auto-apply: {len(eligible)} (Greenhouse + Lever, max {MAX_PER_COMPANY}/company)")
    print(f"Limit: {limit}\n")

    _telegram(f"Internship bot starting. {len(eligible)} eligible applications queued.")

    driver = _make_driver()
    counts = {"applied": 0, "failed": 0, "skipped": 0}

    try:
        for i, job in enumerate(eligible[:limit]):
            # Enforce per-company cap at runtime too (in case we just applied)
            company_key = job.get("company", "").lower()
            if company_counts.get(company_key, 0) >= MAX_PER_COMPANY:
                print(f"\n  Skipping {job.get('company')} — already at {MAX_PER_COMPANY} apps")
                counts["skipped"] += 1
                _log_applied(job, "skipped", applied)
                _save_applied(applied)
                continue

            # Restart driver if it dies
            try:
                driver.current_url
            except Exception:
                print("  Driver died — restarting Chrome...")
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = _make_driver()

            status = apply_to_job(driver, job)
            if status == "applied":
                company_counts[company_key] = company_counts.get(company_key, 0) + 1
            counts[status] += 1
            _log_applied(job, status, applied)
            _save_applied(applied)

            print(f"  [{status.upper()}] ({counts['applied']} done, {counts['failed']} failed, {counts['skipped']} skipped)")

            if counts["applied"] > 0 and counts["applied"] % 25 == 0:
                _telegram(
                    f"Progress: <b>{counts['applied']}</b> submitted, "
                    f"{counts['failed']} failed. Still running..."
                )

            _pause(3.0, 6.0)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        _save_applied(applied)

        summary = (
            f"Run complete.\n"
            f"Applied: <b>{counts['applied']}</b>\n"
            f"Failed: {counts['failed']}\n"
            f"Skipped: {counts['skipped']}\n"
            f"Check applied.json for the full log."
        )
        print(f"\n{summary}")
        _telegram(summary)


if __name__ == "__main__":
    run_auto_apply()
