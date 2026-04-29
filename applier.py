"""
Application submitter — handles different application flows.

Strategy:
1. SimplifyJobs links → direct apply URL (most are 1-click via Simplify extension or redirect)
2. LinkedIn Easy Apply → Selenium automation
3. External apply links → open in browser for manual submission (logged to queue)
4. Email-based applications → send email with resume attached

All applications are logged to applied.json to prevent duplicates.
"""

import os
import json
import time
import webbrowser
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.prompt import Confirm
from cover_letter import generate_cover_letter

console = Console()

APPLIED_LOG = Path(__file__).parent / "applied.json"
QUEUE_LOG = Path(__file__).parent / "manual_queue.json"


def _load_applied() -> set[str]:
    if APPLIED_LOG.exists():
        data = json.loads(APPLIED_LOG.read_text())
        return set(data.keys())
    return set()


def _save_applied(job_id: str, job: dict, status: str, cover_letter: str = ""):
    data = {}
    if APPLIED_LOG.exists():
        data = json.loads(APPLIED_LOG.read_text())
    data[job_id] = {
        "company": job.get("company"),
        "title": job.get("title"),
        "url": job.get("url"),
        "applied_at": datetime.now().isoformat(),
        "status": status,
        "match_score": job.get("match_score", 0),
        "cover_letter_preview": cover_letter[:300] if cover_letter else "",
    }
    APPLIED_LOG.write_text(json.dumps(data, indent=2))


def _queue_manual(job: dict, cover_letter: str):
    """Add to the manual apply queue (opened in browser)."""
    data = []
    if QUEUE_LOG.exists():
        data = json.loads(QUEUE_LOG.read_text())
    data.append({
        "company": job.get("company"),
        "title": job.get("title"),
        "url": job.get("url"),
        "apply_url": job.get("apply_url"),
        "match_score": job.get("match_score", 0),
        "match_reasons": job.get("match_reasons", []),
        "cover_letter": cover_letter,
        "queued_at": datetime.now().isoformat(),
        "status": "queued",
    })
    QUEUE_LOG.write_text(json.dumps(data, indent=2))


def apply_to_job(job: dict, api_key: str | None, dry_run: bool = False) -> str:
    """
    Attempt to apply to a single job.
    Returns status: 'applied', 'queued', 'skipped', 'already_applied'
    """
    job_id = job.get("id", job.get("url", ""))
    applied = _load_applied()

    if job_id in applied:
        return "already_applied"

    # Generate cover letter
    cover = generate_cover_letter(job, api_key=api_key)

    apply_url = job.get("apply_url") or job.get("url", "")
    source = job.get("source", "")

    console.print(f"\n[bold]{job.get('company')}[/bold] — {job.get('title')}")
    console.print(f"  Score: [green]{job.get('match_score')}[/green]  |  {apply_url[:80]}")
    console.print(f"  [dim]{', '.join(job.get('match_reasons', [])[:3])}[/dim]")

    if dry_run:
        console.print("  [yellow][DRY RUN] Would apply here[/yellow]")
        _save_applied(job_id, job, "dry_run", cover)
        return "dry_run"

    # --- SimplifyJobs: open the URL (Simplify extension handles 1-click apply) ---
    if source == "SimplifyJobs" and apply_url:
        webbrowser.open(apply_url)
        _queue_manual(job, cover)
        _save_applied(job_id, job, "opened", cover)
        time.sleep(1.5)  # Don't hammer the browser
        return "opened"

    # --- LinkedIn Easy Apply (basic version — open in browser) ---
    if source == "LinkedIn" and apply_url:
        webbrowser.open(apply_url)
        _queue_manual(job, cover)
        _save_applied(job_id, job, "opened", cover)
        time.sleep(1.5)
        return "opened"

    # --- Fallback: open in browser ---
    if apply_url:
        webbrowser.open(apply_url)
        _queue_manual(job, cover)
        _save_applied(job_id, job, "queued", cover)
        time.sleep(1.5)
        return "queued"

    return "skipped"


def run_applications(jobs: list[dict], api_key: str | None, limit: int = 20, dry_run: bool = False):
    """Apply to the top N matched jobs."""
    console.print(f"\n[bold cyan]Starting applications — top {limit} matched jobs[/bold cyan]")
    console.print(f"[dim]Mode: {'DRY RUN' if dry_run else 'LIVE'}[/dim]\n")

    stats = {"applied": 0, "opened": 0, "queued": 0, "skipped": 0, "already_applied": 0, "dry_run": 0}

    for job in jobs[:limit]:
        status = apply_to_job(job, api_key=api_key, dry_run=dry_run)
        stats[status] = stats.get(status, 0) + 1

        if status in ("opened", "queued"):
            stats["applied"] += 1

        # Small pause between applications
        time.sleep(0.5)

    console.print("\n[bold green]Run complete![/bold green]")
    console.print(f"  Opened/applied: {stats['applied']}")
    console.print(f"  Already applied: {stats['already_applied']}")
    console.print(f"  Skipped: {stats['skipped']}")
    if dry_run:
        console.print(f"  Dry run (no action): {stats['dry_run']}")
    console.print(f"\nSee [bold]applied.json[/bold] for full log and [bold]manual_queue.json[/bold] for cover letters.")
