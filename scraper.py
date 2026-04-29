"""
Job scraper — pulls internship listings from multiple sources.
Sources: SimplifyJobs GitHub, LinkedIn, Wellfound (AngelList), New Grad positions
"""

import requests
import time
from bs4 import BeautifulSoup
from rich.console import Console
from matcher import HEADERS, is_entry_level

console = Console()

SIMPLIFY_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json"
OFFSEASON_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
LINKEDIN_BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
WELLFOUND_URL = "https://wellfound.com/jobs"


def _simplify_item_to_jobs(item: dict, source: str) -> list[dict]:
    return [
        {
            "source": source,
            "id": f"{source.lower()}_{item.get('id', '')}_{loc}",
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": loc,
            "url": item.get("url", ""),
            "date_posted": item.get("date_updated", ""),
            "description": item.get("notes", ""),
            "apply_url": item.get("url", ""),
            "is_remote": "remote" in loc.lower(),
            "sponsorship": item.get("sponsorship", ""),
            "terms": item.get("terms", []),
        }
        for loc in item.get("locations", ["Remote"])
    ]


def _fetch_simplify_url(url: str, source: str, label: str) -> list[dict]:
    console.print(f"[cyan]Fetching {label}...[/cyan]")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        jobs = []
        for item in r.json():
            if not item.get("active", True):
                continue
            if not is_entry_level(item.get("title", "")):
                continue
            jobs.extend(_simplify_item_to_jobs(item, source))
        console.print(f"[green]{label}: {len(jobs)} listings[/green]")
        return jobs
    except Exception as e:
        console.print(f"[red]{label} failed: {e}[/red]")
        return []


def fetch_simplify_jobs() -> list[dict]:
    return _fetch_simplify_url(SIMPLIFY_URL, "SimplifyJobs", "SimplifyJobs")


def fetch_new_grad_jobs() -> list[dict]:
    return _fetch_simplify_url(OFFSEASON_URL, "NewGrad", "New Grad positions")


def fetch_linkedin_jobs(keywords: str = "software engineer internship", location: str = "San Francisco Bay Area", pages: int = 4) -> list[dict]:
    console.print(f"[cyan]Fetching LinkedIn: '{keywords}' in '{location}'...[/cyan]")
    jobs = []
    for page in range(pages):
        params = {
            "keywords": keywords,
            "location": location,
            "f_TP": "1",
            "f_JT": "I",
            "f_E": "1",
            "start": page * 25,
            "count": 25,
        }
        try:
            r = requests.get(LINKEDIN_BASE, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            found = 0
            for card in soup.select("li"):
                title_el = card.select_one("h3.base-search-card__title, .job-search-card__title")
                company_el = card.select_one("h4.base-search-card__subtitle, .job-search-card__company-name")
                location_el = card.select_one(".job-search-card__location")
                date_el = card.select_one("time")
                link_el = card.select_one("a.base-card__full-link, a[data-tracking-control-name]")
                if not title_el or not link_el:
                    continue
                job_url = link_el.get("href", "").split("?")[0]
                loc_text = location_el.get_text(strip=True) if location_el else location
                jobs.append({
                    "source": "LinkedIn",
                    "id": f"linkedin_{hash(job_url)}",
                    "title": title_el.get_text(strip=True),
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "location": loc_text,
                    "url": job_url,
                    "date_posted": date_el.get("datetime", "") if date_el else "",
                    "description": "",
                    "apply_url": job_url,
                    "is_remote": "remote" in loc_text.lower(),
                    "sponsorship": "",
                    "terms": [],
                })
                found += 1
            if found == 0:
                break
            time.sleep(2)
        except Exception as e:
            console.print(f"[red]LinkedIn page {page} failed: {e}[/red]")
            break
    console.print(f"[green]LinkedIn: {len(jobs)} listings[/green]")
    return jobs


def fetch_wellfound_jobs() -> list[dict]:
    console.print("[cyan]Fetching Wellfound (startup internships)...[/cyan]")
    jobs = []
    for query in ["software engineer intern", "software developer intern", "backend intern", "full stack intern"]:
        try:
            r = requests.get(WELLFOUND_URL, params={"q": query, "job_type": "internship", "remote": "true"}, headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select("div[class*='JobListing'], div[class*='job-listing'], div[data-test='JobListing']"):
                title_el = card.select_one("a[class*='title'], h2, h3")
                company_el = card.select_one("a[class*='company'], span[class*='company']")
                location_el = card.select_one("span[class*='location']")
                link_el = card.select_one("a[href*='/jobs/']")
                if not title_el:
                    continue
                href = link_el.get("href", "") if link_el else ""
                job_url = f"https://wellfound.com{href}" if href.startswith("/") else href
                jobs.append({
                    "source": "Wellfound",
                    "id": f"wellfound_{hash(job_url)}",
                    "title": title_el.get_text(strip=True),
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "location": location_el.get_text(strip=True) if location_el else "Remote",
                    "url": job_url,
                    "date_posted": "",
                    "description": "",
                    "apply_url": job_url,
                    "is_remote": True,
                    "sponsorship": "",
                    "terms": [],
                })
            time.sleep(2)
        except Exception as e:
            console.print(f"[red]Wellfound '{query}' failed: {e}[/red]")
    console.print(f"[green]Wellfound: {len(jobs)} listings[/green]")
    return jobs


def deduplicate(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for job in jobs:
        key = job.get("url", "").split("?")[0].rstrip("/")
        if key and key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def scrape_all() -> list[dict]:
    all_jobs = []

    all_jobs.extend(fetch_simplify_jobs())
    all_jobs.extend(fetch_new_grad_jobs())

    linkedin_searches = [
        ("software engineer internship", "San Francisco Bay Area"),
        ("software developer intern", "San Francisco Bay Area"),
        ("backend engineer intern", "San Francisco Bay Area"),
        ("full stack intern", "San Francisco Bay Area"),
        ("software engineer internship", "United States"),
        ("Python developer internship", "United States"),
        ("React developer internship", "United States"),
    ]
    for kw, loc in linkedin_searches:
        all_jobs.extend(fetch_linkedin_jobs(keywords=kw, location=loc, pages=4))
        time.sleep(3)

    all_jobs.extend(fetch_wellfound_jobs())

    deduped = deduplicate(all_jobs)
    console.print(f"\n[bold green]Total unique listings: {len(deduped)}[/bold green]")
    return deduped
