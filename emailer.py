"""
Daily email digest — sends a summary of new applications to your Gmail.
Uses Gmail SMTP with an app password (no OAuth needed).
"""

import smtplib
import json
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


APPLIED_LOG = Path(__file__).parent / "applied.json"
QUEUE_LOG = Path(__file__).parent / "manual_queue.json"


def _load_todays_applications() -> list[dict]:
    if not APPLIED_LOG.exists():
        return []
    data = json.loads(APPLIED_LOG.read_text())
    cutoff = datetime.now() - timedelta(hours=24)
    recent = []
    for job_id, entry in data.items():
        try:
            applied_at = datetime.fromisoformat(entry.get("applied_at", ""))
            if applied_at >= cutoff:
                recent.append(entry)
        except Exception:
            continue
    return sorted(recent, key=lambda x: x.get("match_score", 0), reverse=True)


def _load_cover_letters() -> dict:
    """Return cover letters keyed by company+title."""
    if not QUEUE_LOG.exists():
        return {}
    data = json.loads(QUEUE_LOG.read_text())
    result = {}
    cutoff = datetime.now() - timedelta(hours=24)
    for entry in data:
        try:
            queued_at = datetime.fromisoformat(entry.get("queued_at", ""))
            if queued_at >= cutoff:
                key = f"{entry.get('company', '')}|{entry.get('title', '')}"
                result[key] = entry.get("cover_letter", "")
        except Exception:
            continue
    return result


def build_email_html(applications: list[dict], cover_letters: dict) -> str:
    total = len(applications)
    bay_area = sum(1 for a in applications if a.get("is_bay_area"))
    remote = sum(1 for a in applications if a.get("is_remote"))
    housing = sum(1 for a in applications if a.get("has_housing"))
    date_str = datetime.now().strftime("%B %d, %Y")

    rows = ""
    for app in applications:
        key = f"{app.get('company', '')}|{app.get('title', '')}"
        cl = cover_letters.get(key, "")
        cl_html = f"<details><summary style='cursor:pointer;color:#4f46e5;font-size:12px;'>View cover letter</summary><p style='font-size:12px;color:#374151;background:#f9fafb;padding:12px;border-radius:6px;white-space:pre-wrap;'>{cl}</p></details>" if cl else ""

        badge = ""
        if app.get("is_bay_area"):
            badge = "<span style='background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:999px;'>Bay Area</span>"
        elif app.get("is_remote"):
            badge = "<span style='background:#dbeafe;color:#1e40af;font-size:11px;padding:2px 8px;border-radius:999px;'>Remote</span>"
        if app.get("has_housing"):
            badge += " <span style='background:#fef9c3;color:#854d0e;font-size:11px;padding:2px 8px;border-radius:999px;'>Housing/Stipend</span>"

        rows += f"""
        <tr>
          <td style='padding:12px 8px;border-bottom:1px solid #f3f4f6;'>
            <strong style='color:#111827;'>{app.get('company', '')}</strong><br>
            <span style='color:#6b7280;font-size:13px;'>{app.get('title', '')}</span><br>
            <span style='color:#9ca3af;font-size:12px;'>{app.get('location', '')}</span>
          </td>
          <td style='padding:12px 8px;border-bottom:1px solid #f3f4f6;text-align:center;'>
            <span style='font-size:18px;font-weight:700;color:#4f46e5;'>{app.get('match_score', 0)}</span>
          </td>
          <td style='padding:12px 8px;border-bottom:1px solid #f3f4f6;'>{badge}</td>
          <td style='padding:12px 8px;border-bottom:1px solid #f3f4f6;'>
            <a href='{app.get('url', '')}' style='color:#4f46e5;font-size:12px;'>View posting</a><br>
            {cl_html}
          </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f9fafb;margin:0;padding:0;'>
      <div style='max-width:700px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);'>

        <div style='background:#4f46e5;padding:28px 32px;'>
          <h1 style='color:#ffffff;margin:0;font-size:22px;'>Internship Bot Daily Report</h1>
          <p style='color:#c7d2fe;margin:6px 0 0;font-size:14px;'>{date_str}</p>
        </div>

        <div style='padding:24px 32px;display:flex;gap:16px;background:#f8faff;border-bottom:1px solid #e5e7eb;'>
          <div style='text-align:center;flex:1;'>
            <div style='font-size:32px;font-weight:700;color:#4f46e5;'>{total}</div>
            <div style='font-size:12px;color:#6b7280;margin-top:4px;'>Applications Sent</div>
          </div>
          <div style='text-align:center;flex:1;'>
            <div style='font-size:32px;font-weight:700;color:#059669;'>{bay_area}</div>
            <div style='font-size:12px;color:#6b7280;margin-top:4px;'>Bay Area Local</div>
          </div>
          <div style='text-align:center;flex:1;'>
            <div style='font-size:32px;font-weight:700;color:#2563eb;'>{remote}</div>
            <div style='font-size:12px;color:#6b7280;margin-top:4px;'>Remote</div>
          </div>
          <div style='text-align:center;flex:1;'>
            <div style='font-size:32px;font-weight:700;color:#d97706;'>{housing}</div>
            <div style='font-size:12px;color:#6b7280;margin-top:4px;'>Housing/Stipend</div>
          </div>
        </div>

        <div style='padding:24px 32px;'>
          <table style='width:100%;border-collapse:collapse;'>
            <thead>
              <tr style='border-bottom:2px solid #e5e7eb;'>
                <th style='text-align:left;padding:8px;color:#374151;font-size:13px;'>Company</th>
                <th style='text-align:center;padding:8px;color:#374151;font-size:13px;'>Score</th>
                <th style='text-align:left;padding:8px;color:#374151;font-size:13px;'>Type</th>
                <th style='text-align:left;padding:8px;color:#374151;font-size:13px;'>Links</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>

        <div style='padding:16px 32px;background:#f8faff;border-top:1px solid #e5e7eb;text-align:center;'>
          <p style='color:#9ca3af;font-size:12px;margin:0;'>Internship Bot — running on your PC overnight</p>
        </div>
      </div>
    </body>
    </html>
    """
    return html


def send_digest(gmail_user: str, gmail_app_password: str, to_email: str):
    """Send the daily digest email via Gmail SMTP."""
    applications = _load_todays_applications()
    cover_letters = _load_cover_letters()

    if not applications:
        print("No applications in the last 24 hours — skipping email.")
        return

    html = build_email_html(applications, cover_letters)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Internship Bot — {len(applications)} applications sent today"
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
        print(f"Digest sent to {to_email} — {len(applications)} applications.")
    except Exception as e:
        print(f"Email failed: {e}")
        print("Make sure GMAIL_APP_PASSWORD is set in your .env file.")
        print("Get one at: myaccount.google.com/apppasswords")
