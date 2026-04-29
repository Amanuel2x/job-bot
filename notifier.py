"""
Notifier — sends updates via Telegram.
Replaces the email digest as the primary notification channel.
Also sends email as a backup if configured.
"""

import json
import os
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

APPLIED_LOG = Path(__file__).parent / "applied.json"
QUEUE_LOG = Path(__file__).parent / "manual_queue.json"


def _load_recent(hours: int = 24) -> list[dict]:
    if not APPLIED_LOG.exists():
        return []
    data = json.loads(APPLIED_LOG.read_text())
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = []
    for entry in data.values():
        try:
            if datetime.fromisoformat(entry.get("applied_at", "")) >= cutoff:
                recent.append(entry)
        except Exception:
            continue
    return sorted(recent, key=lambda x: x.get("match_score", 0), reverse=True)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def build_telegram_digest(applications: list[dict]) -> str:
    if not applications:
        return "Job Bot ran but found no new applications in the last 24 hours."

    total = len(applications)
    bay = sum(1 for a in applications if a.get("is_bay_area"))
    remote = sum(1 for a in applications if a.get("is_remote"))
    housing = sum(1 for a in applications if a.get("has_housing"))
    date_str = datetime.now().strftime("%b %d, %Y %I:%M %p")

    lines = [
        f"<b>Job Bot Report</b> — {date_str}",
        f"",
        f"Applied: <b>{total}</b>  |  Bay Area: <b>{bay}</b>  |  Remote: <b>{remote}</b>  |  Housing: <b>{housing}</b>",
        f"",
        f"<b>Top Applications:</b>",
    ]

    for app in applications[:15]:
        flags = []
        if app.get("is_bay_area"):
            flags.append("Bay Area")
        elif app.get("is_remote"):
            flags.append("Remote")
        if app.get("has_housing"):
            flags.append("Housing")
        flag_str = " · ".join(flags)
        url = app.get("url", "")
        company = app.get("company", "")
        title = app.get("title", "")
        score = app.get("match_score", 0)

        if url:
            lines.append(f"• <a href='{url}'>{company}</a> — {title} [{score}] {flag_str}")
        else:
            lines.append(f"• {company} — {title} [{score}] {flag_str}")

    if total > 15:
        lines.append(f"\n...and {total - 15} more. Check the dashboard for the full list.")

    return "\n".join(lines)


def notify_run_complete(total_applied: int, new_matches: int, token: str, chat_id: str):
    """Quick ping when a run finishes."""
    msg = (
        f"Run complete. "
        f"<b>{total_applied}</b> applications sent, "
        f"<b>{new_matches}</b> new matches found."
    )
    send_telegram(token, chat_id, msg)


def send_digest(token: str = None, chat_id: str = None,
                gmail_user: str = None, gmail_app_password: str = None,
                notify_email: str = None):
    """
    Send digest via Telegram (primary) and email (backup).
    Falls back gracefully if either isn't configured.
    """
    applications = _load_recent(hours=24)

    # Telegram
    if token and chat_id:
        msg = build_telegram_digest(applications)
        ok = send_telegram(token, chat_id, msg)
        if ok:
            print(f"Telegram digest sent — {len(applications)} applications.")
        else:
            print("Telegram digest failed.")
    else:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing).")

    # Email backup
    if gmail_user and gmail_app_password and notify_email:
        try:
            from emailer import send_digest as send_email_digest
            send_email_digest(gmail_user, gmail_app_password, notify_email)
        except Exception as e:
            print(f"Email backup failed: {e}")
