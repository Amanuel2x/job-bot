#!/usr/bin/env python3
"""
Internship Bot

Usage:
  python main.py                   # Full run: scrape → match → apply → email digest
  python main.py --dry-run         # See matches without opening any links
  python main.py --scrape-only     # Scrape and save matches.json, stop there
  python main.py --apply-only      # Apply from existing matches.json
  python main.py --email-only      # Send digest of today's applications to Gmail
  python main.py --report          # Print stats from applied.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

MATCHES_FILE = Path(__file__).parent / "matches.json"


def load_env() -> dict:
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "gmail_user": os.getenv("GMAIL_USER"),
        "gmail_app_password": os.getenv("GMAIL_APP_PASSWORD"),
        "notify_email": os.getenv("NOTIFY_EMAIL", "amanuelalexabu@gmail.com"),
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        "min_score": int(os.getenv("MIN_MATCH_SCORE", "25")),
        "apply_limit": int(os.getenv("APPLY_LIMIT_PER_RUN", "150")),
        "dry_run": os.getenv("DRY_RUN", "false").lower() == "true",
    }


def print_matches_table(jobs: list[dict]):
    table = Table(title=f"Matched Internships ({len(jobs)} total)", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", style="green", width=6)
    table.add_column("Company", style="bold", width=22)
    table.add_column("Title", width=30)
    table.add_column("Location", width=18)
    table.add_column("Flags", width=20)

    for i, job in enumerate(jobs[:100], 1):
        flags = []
        if job.get("is_bay_area"):
            flags.append("[green]Bay Area[/green]")
        elif job.get("is_remote"):
            flags.append("[blue]Remote[/blue]")
        if job.get("has_housing"):
            flags.append("[yellow]Housing[/yellow]")
        table.add_row(
            str(i),
            str(job.get("match_score", 0)),
            job.get("company", "")[:22],
            job.get("title", "")[:30],
            job.get("location", "")[:18],
            " ".join(flags),
        )
    console.print(table)


def print_report():
    applied_file = Path(__file__).parent / "applied.json"
    if not applied_file.exists():
        console.print("[yellow]No applications logged yet.[/yellow]")
        return
    data = json.loads(applied_file.read_text())
    console.print(f"\n[bold]Total applications logged:[/bold] {len(data)}")
    by_status = {}
    for v in data.values():
        s = v.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    for status, count in sorted(by_status.items()):
        console.print(f"  {status}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Internship Bot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--apply-only", action="store_true")
    parser.add_argument("--email-only", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    env = load_env()

    if args.report:
        print_report()
        return

    if args.email_only:
        from notifier import send_digest
        send_digest(
            token=env["telegram_token"],
            chat_id=env["telegram_chat_id"],
            gmail_user=env["gmail_user"],
            gmail_app_password=env["gmail_app_password"],
            notify_email=env["notify_email"],
        )
        return

    if args.apply_only:
        if not MATCHES_FILE.exists():
            console.print("[red]No matches.json found. Run without --apply-only first.[/red]")
            sys.exit(1)
        jobs = json.loads(MATCHES_FILE.read_text())
        console.print(f"[cyan]Loaded {len(jobs)} matches from matches.json[/cyan]")
        print_matches_table(jobs)
        from applier import run_applications
        run_applications(jobs, api_key=env["api_key"], limit=env["apply_limit"], dry_run=args.dry_run or env["dry_run"])
        return

    # Full run
    console.print("[bold cyan]Internship Bot Starting[/bold cyan]\n")
    from scraper import scrape_all
    from scraper_platforms import scrape_platforms
    jobs = scrape_all()
    jobs += scrape_platforms()

    if not jobs:
        console.print("[red]No jobs found. Check your connection.[/red]")
        sys.exit(1)

    from matcher import filter_and_rank
    matched = filter_and_rank(jobs, min_score=env["min_score"])

    bay = sum(1 for j in matched if j.get("is_bay_area"))
    remote = sum(1 for j in matched if j.get("is_remote"))
    housing = sum(1 for j in matched if j.get("has_housing"))

    console.print(f"\n[bold green]{len(matched)} matched[/bold green]  |  {bay} Bay Area  |  {remote} Remote  |  {housing} with housing/stipend")

    MATCHES_FILE.write_text(json.dumps(matched, indent=2))
    console.print(f"Saved to matches.json\n")

    print_matches_table(matched)

    if args.scrape_only:
        return

    from applier import run_applications
    run_applications(
        matched,
        api_key=env["api_key"],
        limit=env["apply_limit"],
        dry_run=args.dry_run or env["dry_run"],
    )

    # Send notifications after applying
    if not (args.dry_run or env["dry_run"]):
        console.print("\n[cyan]Sending notifications...[/cyan]")
        from notifier import send_digest
        send_digest(
            token=env["telegram_token"],
            chat_id=env["telegram_chat_id"],
            gmail_user=env["gmail_user"],
            gmail_app_password=env["gmail_app_password"],
            notify_email=env["notify_email"],
        )


if __name__ == "__main__":
    main()
