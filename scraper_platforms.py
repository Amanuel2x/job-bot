"""
Platform-specific scrapers for big company recruiting sites.
Targets Greenhouse, Lever, and Workday — the three platforms
that cover the majority of tech job postings.
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from rich.console import Console
from matcher import HEADERS, is_entry_level

console = Console()

GREENHOUSE_COMPANIES = [
    ("stripe", "stripe"),
    ("airbnb", "airbnb"),
    ("notion", "notion"),
    ("figma", "figma"),
    ("dropbox", "dropbox"),
    ("coinbase", "coinbase"),
    ("robinhood", "robinhood"),
    ("doordash", "doordash"),
    ("instacart", "instacart"),
    ("twilio", "twilio"),
    ("cloudflare", "cloudflare"),
    ("databricks", "databricks"),
    ("snowflake", "snowflake"),
    ("brex", "brex"),
    ("plaid", "plaid"),
    ("scale-ai", "scaleai"),
    ("benchling", "benchling"),
    ("lattice", "lattice"),
    ("gusto", "gusto"),
    ("rippling", "rippling"),
    ("verkada", "verkada"),
    ("planet", "planet"),
    ("chime", "chime"),
    ("opendoor", "opendoor"),
    ("lyft", "lyft"),
    ("duolingo", "duolingo"),
    ("klaviyo", "klaviyo"),
    ("mongodb", "mongodb"),
    ("hashicorp", "hashicorp"),
    ("mixpanel", "mixpanel"),
    ("asana", "asana"),
    ("zendesk", "zendesk"),
    ("okta", "okta"),
    ("pagerduty", "pagerduty"),
]

LEVER_COMPANIES = [
    ("netflix", "Netflix"),
    ("reddit", "Reddit"),
    ("twitter", "Twitter"),
    ("squarespace", "Squarespace"),
    ("canva", "Canva"),
    ("atlassian", "Atlassian"),
    ("shopify", "Shopify"),
    ("hubspot", "HubSpot"),
    ("intercom", "Intercom"),
    ("segment", "Segment"),
    ("mixpanel", "Mixpanel"),
    ("amplitude", "Amplitude"),
    ("airtable", "Airtable"),
    ("linear", "Linear"),
    ("vercel", "Vercel"),
    ("retool", "Retool"),
    ("mercury", "Mercury"),
    ("ramp", "Ramp"),
    ("carta", "Carta"),
    ("checkr", "Checkr"),
    ("faire", "Faire"),
    ("coda", "Coda"),
    ("loom", "Loom"),
    ("miro", "Miro"),
    ("figma", "Figma"),
]

WORKDAY_COMPANIES = [
    ("raytheon", "https://globalhr.wd5.myworkdayjobs.com/wday/cxs/REC_RTX_Ext_Gateway/jobs"),
    ("amazon", "https://amazon.jobs/en/search.json"),
    ("microsoft", "https://gdc.taleo.net/careersection/10000/jobsearch.ftl"),
    ("nvidia", "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/NVIDIAExternalCareerSite/jobs"),
    ("apple", "https://jobs.apple.com/api/role/search"),
    ("meta", "https://www.metacareers.com/graphql"),
    ("salesforce", "https://salesforce.wd12.myworkdayjobs.com/wday/cxs/External_Career_Site/jobs"),
    ("adobe", "https://adobe.wd5.myworkdayjobs.com/wday/cxs/external_experienced/jobs"),
    ("qualcomm", "https://qualcomm.wd5.myworkdayjobs.com/wday/cxs/External/jobs"),
    ("boeing", "https://boeing.wd1.myworkdayjobs.com/wday/cxs/EXTERNAL_CAREERS/jobs"),
]

WORKDAY_PAYLOAD = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "software intern",
}

INTERN_KEYWORDS = [
    "intern", "job", "co-op", "coop", "new grad", "university",
    "student", "early career",
]

SWE_KEYWORDS = [
    "software engineer", "software developer", "swe", "backend engineer",
    "frontend engineer", "full stack", "fullstack", "python", "data engineer",
]


def _is_intern_role(title: str) -> bool:
    if not is_entry_level(title):
        return False
    t = title.lower()
    return any(kw in t for kw in INTERN_KEYWORDS) or any(kw in t for kw in SWE_KEYWORDS)


def fetch_greenhouse(company_slug: str, company_name: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for job in r.json().get("jobs", []):
            title = job.get("title", "")
            if not _is_intern_role(title):
                continue
            location = job.get("location", {}).get("name", "")
            apply_url = job.get("absolute_url", "")
            jobs.append({
                "source": "Greenhouse",
                "id": f"greenhouse_{job.get('id', '')}",
                "title": title,
                "company": company_name.title(),
                "location": location,
                "url": apply_url,
                "date_posted": job.get("updated_at", ""),
                "description": BeautifulSoup(job.get("content", ""), "html.parser").get_text()[:500],
                "apply_url": apply_url,
                "is_remote": "remote" in location.lower(),
                "sponsorship": "",
                "terms": [],
            })
        return jobs
    except Exception:
        return []


def fetch_lever(company_slug: str, company_name: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for job in r.json():
            title = job.get("text", "")
            if not _is_intern_role(title):
                continue
            categories = job.get("categories", {})
            location = categories.get("location", categories.get("office", ""))
            apply_url = job.get("hostedUrl", "")
            jobs.append({
                "source": "Lever",
                "id": f"lever_{job.get('id', '')}",
                "title": title,
                "company": company_name,
                "location": location,
                "url": apply_url,
                "date_posted": "",
                "description": job.get("descriptionPlain", "")[:500],
                "apply_url": apply_url,
                "is_remote": "remote" in location.lower(),
                "sponsorship": "",
                "terms": [],
            })
        return jobs
    except Exception:
        return []


def fetch_workday(company: str, api_url: str) -> list[dict]:
    try:
        r = requests.post(api_url, json=WORKDAY_PAYLOAD, headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for job in r.json().get("jobPostings", []):
            title = job.get("title", "")
            if not _is_intern_role(title):
                continue
            external_path = job.get("externalPath", "")
            base = api_url.split("/wday/")[0] if "/wday/" in api_url else ""
            apply_url = f"{base}{external_path}" if external_path else ""
            location_raw = job.get("locationsText", "")
            jobs.append({
                "source": "Workday",
                "id": f"workday_{company}_{hash(title + location_raw)}",
                "title": title,
                "company": company.title(),
                "location": location_raw,
                "url": apply_url,
                "date_posted": job.get("postedOn", ""),
                "description": job.get("jobDescription", "")[:500],
                "apply_url": apply_url,
                "is_remote": "remote" in location_raw.lower(),
                "sponsorship": "",
                "terms": [],
            })
        return jobs
    except Exception:
        return []


def _fetch_parallel(fetch_fn, companies: list, workers: int = 8) -> list[dict]:
    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_fn, slug, name): name for slug, name in companies}
        for future in as_completed(futures):
            jobs.extend(future.result())
    return jobs


def fetch_all_greenhouse() -> list[dict]:
    console.print("[cyan]Fetching Greenhouse companies...[/cyan]")
    jobs = _fetch_parallel(fetch_greenhouse, GREENHOUSE_COMPANIES)
    console.print(f"[green]Greenhouse: {len(jobs)} intern listings[/green]")
    return jobs


def fetch_all_lever() -> list[dict]:
    console.print("[cyan]Fetching Lever companies...[/cyan]")
    jobs = _fetch_parallel(fetch_lever, LEVER_COMPANIES)
    console.print(f"[green]Lever: {len(jobs)} intern listings[/green]")
    return jobs


def fetch_all_workday() -> list[dict]:
    console.print("[cyan]Fetching Workday companies...[/cyan]")
    jobs = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_workday, company, url): company for company, url in WORKDAY_COMPANIES}
        for future in as_completed(futures):
            jobs.extend(future.result())
    console.print(f"[green]Workday: {len(jobs)} intern listings[/green]")
    return jobs


def scrape_platforms() -> list[dict]:
    all_jobs = []
    all_jobs.extend(fetch_all_greenhouse())
    all_jobs.extend(fetch_all_lever())
    all_jobs.extend(fetch_all_workday())
    console.print(f"[bold green]Platform scrapers: {len(all_jobs)} total[/bold green]")
    return all_jobs
