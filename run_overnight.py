#!/usr/bin/env python3
"""
Overnight runner — scrapes jobs, matches them, then auto-applies hands-free.
Just run this and go to sleep. Telegram will ping you when done.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

MATCHES_FILE = Path(__file__).parent / "matches.json"


MATCHES_AGE_HOURS = 12  # rescrape if matches.json is older than this


def _matches_are_fresh() -> bool:
    if not MATCHES_FILE.exists():
        return False
    age_hours = (Path(MATCHES_FILE).stat().st_mtime - 0) / 3600
    import time as _t
    age_hours = (_t.time() - MATCHES_FILE.stat().st_mtime) / 3600
    return age_hours < MATCHES_AGE_HOURS


def main():
    console.print("[bold cyan]Overnight Bot Starting[/bold cyan]\n")

    if _matches_are_fresh():
        console.print(f"[green]matches.json is fresh — skipping scrape, picking up where we left off.[/green]\n")
        matched = json.loads(MATCHES_FILE.read_text())
    else:
        # Step 1: Scrape
        console.print("[cyan]Step 1/3 — Scraping jobs...[/cyan]")
        from scraper import scrape_all
        from scraper_platforms import scrape_platforms
        jobs = scrape_all()
        jobs += scrape_platforms()

        if not jobs:
            console.print("[red]No jobs found. Check your connection.[/red]")
            sys.exit(1)

        # Step 2: Match
        console.print("\n[cyan]Step 2/3 — Matching and ranking...[/cyan]")
        from matcher import filter_and_rank
        min_score = int(os.getenv("MIN_MATCH_SCORE", "25"))
        matched = filter_and_rank(jobs, min_score=min_score)

        bay = sum(1 for j in matched if j.get("is_bay_area"))
        remote = sum(1 for j in matched if j.get("is_remote"))
        housing = sum(1 for j in matched if j.get("has_housing"))

        console.print(f"\n[bold green]{len(matched)} matched[/bold green]  |  {bay} Bay Area  |  {remote} Remote  |  {housing} with housing")
        MATCHES_FILE.write_text(json.dumps(matched, indent=2))
        console.print(f"Saved to matches.json\n")

    # Step 3: Auto-apply — skips anything already in applied.json
    console.print("[cyan]Auto-applying (hands-free, resuming from last position)...[/cyan]")
    from auto_applier import run_auto_apply
    limit = int(os.getenv("APPLY_LIMIT_PER_RUN", "200"))
    run_auto_apply(limit=limit)


if __name__ == "__main__":
    main()
