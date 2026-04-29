"""
Job matcher — scores each listing 0-100 against your profile.
Also filters for housing/stipend and Bay Area local preferences.
"""

from __future__ import annotations
from profile import PROFILE

prefs = PROFILE["preferences"]
skills = PROFILE["skills"]

ALL_SKILLS = set()
for skill_group in skills.values():
    for s in skill_group:
        ALL_SKILLS.add(s.lower())

# Canonical senior/degree-required role filter — shared with scrapers
SENIOR_KEYWORDS = [
    "senior", "staff", "principal", "lead ", "manager", "director",
    "architect", "vp ", "vice president", "head of", "phd", "ph.d",
    "5+ years", "7+ years", "10+ years", "3+ years experience",
]

BAY_AREA_KEYWORDS = [
    "san francisco", "sf", "bay area", "oakland", "berkeley", "san jose",
    "santa clara", "sunnyvale", "mountain view", "palo alto", "menlo park",
    "redwood city", "san mateo", "burlingame", "foster city", "fremont",
    "hayward", "walnut creek", "emeryville", "south san francisco",
    "san ramon", "pleasanton", "livermore", "concord", "richmond",
    "silicon valley", "east bay", "south bay", "peninsula", "marin",
    "sausalito", "mill valley", "san rafael", "novato", "ca, usa",
    "california", ", ca",
]

HOUSING_KEYWORDS = [
    "housing stipend", "relocation", "housing provided", "corporate housing",
    "housing assistance", "moving stipend", "relocation package",
    "housing allowance", "furnished", "intern housing", "subsidized housing",
    "housing support", "relocation assistance", "accommodation",
]

MAJOR_CITY_KEYWORDS = [
    "new york", "nyc", "seattle", "austin", "boston", "chicago",
    "los angeles", "la,", "denver", "atlanta", "raleigh", "washington dc",
    "washington, dc", "san diego", "portland", "minneapolis",
]

HIGH_STIPEND_COMPANIES = {
    "google", "meta", "apple", "amazon", "microsoft", "stripe", "airbnb",
    "uber", "lyft", "salesforce", "twitter", "netflix", "nvidia", "adobe",
    "linkedin", "pinterest", "dropbox", "square", "block", "palantir",
    "databricks", "snowflake", "figma", "notion", "coinbase", "robinhood",
    "github", "shopify", "twilio", "cloudflare", "doordash", "instacart",
    "openai", "anthropic", "scale ai", "waymo", "tesla",
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def is_entry_level(title: str) -> bool:
    """Returns False for senior/staff/manager/degree-required roles."""
    t = title.lower()
    return not any(kw in t for kw in SENIOR_KEYWORDS)


def _text(job: dict) -> str:
    return " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("description", ""),
        job.get("location", ""),
        job.get("sponsorship", ""),
        " ".join(job.get("terms", [])),
    ]).lower()


def is_bay_area(job: dict) -> bool:
    loc = job.get("location", "").lower()
    return any(kw in loc for kw in BAY_AREA_KEYWORDS)


def is_remote(job: dict) -> bool:
    loc = job.get("location", "").lower()
    return job.get("is_remote", False) or "remote" in loc


def has_housing_or_stipend(job: dict, text: str = None) -> bool:
    if text is None:
        text = _text(job)
    company = job.get("company", "").lower()
    if any(c in company for c in HIGH_STIPEND_COMPANIES):
        return True
    return any(kw in text for kw in HOUSING_KEYWORDS)


def is_major_city_with_stipend(job: dict) -> bool:
    loc = job.get("location", "").lower()
    company = job.get("company", "").lower()
    return (
        any(kw in loc for kw in MAJOR_CITY_KEYWORDS)
        and any(c in company for c in HIGH_STIPEND_COMPANIES)
    )


def passes_location_filter(job: dict) -> bool:
    return (
        is_bay_area(job)
        or is_remote(job)
        or has_housing_or_stipend(job)
        or is_major_city_with_stipend(job)
    )


def score_job(job: dict) -> tuple[int, list[str]]:
    text = _text(job)
    title = job.get("title", "").lower()
    source = job.get("source", "")
    score = 0
    reasons = []

    if not is_entry_level(title):
        return 0, ["Excluded: senior/degree role"], False, False, False

    for bad in prefs["exclude_keywords"]:
        if bad.lower() in text:
            return 0, [f"Excluded: '{bad}'"], False, False, False

    # Role match (up to 30 pts)
    for role in prefs["roles"]:
        if role.lower() in title:
            score += 30
            reasons.append(f"Title match: '{role}'")
            break
    else:
        if "intern" in title and any(w in title for w in ["software", "engineer", "develop", "tech", "python", "react"]):
            score += 20
            reasons.append("Intern + tech keyword")
        elif "intern" in title:
            score += 10
            reasons.append("Intern role")
        elif source in ("SimplifyJobs", "NewGrad") and any(w in title for w in ["software", "engineer", "developer", "swe", "backend", "frontend", "fullstack", "full stack", "python", "data"]):
            score += 25
            reasons.append(f"SWE role: '{job.get('title', '')[:40]}'")
        elif source in ("SimplifyJobs", "NewGrad"):
            score += 10
            reasons.append("Tech internship listing")

    # Skill match (up to 40 pts)
    matched_skills = [s for s in ALL_SKILLS if s in text]
    skill_score = min(40, len(matched_skills) * 4)
    score += skill_score
    if matched_skills:
        reasons.append(f"Skills: {', '.join(sorted(matched_skills)[:6])}")

    # Preferred keywords (up to 20 pts)
    pref_matches = [kw for kw in prefs["preferred_keywords"] if kw.lower() in text]
    score += min(20, len(pref_matches) * 3)
    if pref_matches:
        reasons.append(f"Keywords: {', '.join(pref_matches[:4])}")

    # Location bonuses
    bay = is_bay_area(job)
    remote = is_remote(job)
    housing = has_housing_or_stipend(job, text)

    if bay:
        score += 15
        reasons.append("Bay Area local")
    elif remote:
        score += 10
        reasons.append("Remote")

    if housing:
        score += 10
        reasons.append("Housing/stipend offered")
    elif is_major_city_with_stipend(job):
        score += 5
        reasons.append("Major city + known company (stipend likely)")

    return min(score, 100), reasons, bay, remote, housing


def filter_and_rank(jobs: list[dict], min_score: int = 25) -> list[dict]:
    scored = []
    for job in jobs:
        if not passes_location_filter(job):
            continue
        result = score_job(job)
        score, reasons, bay, remote, housing = result
        if score >= min_score:
            job["match_score"] = score
            job["match_reasons"] = reasons
            job["is_bay_area"] = bay
            job["is_remote"] = remote
            job["has_housing"] = housing
            scored.append(job)

    scored.sort(key=lambda j: j["match_score"], reverse=True)
    return scored
