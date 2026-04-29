"""
AI cover letter generator — uses Claude to write a tailored cover letter for each job.
Falls back to a template if no API key is set.
"""

import os
from profile import PROFILE

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


def _pick_best_projects(job: dict) -> list[dict]:
    """Choose the 2-3 most relevant projects for this job."""
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    projects = PROFILE["projects"]
    scored = []
    for p in projects:
        tech_text = " ".join(p["tech"]).lower()
        desc_text = p["description"].lower()
        combined = tech_text + " " + desc_text
        overlap = sum(1 for word in combined.split() if word in text)
        scored.append((overlap, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:3]]


def generate_cover_letter(job: dict, api_key: str | None = None) -> str:
    """Generate a tailored cover letter for the given job."""
    best_projects = _pick_best_projects(job)
    project_bullets = "\n".join(
        f"- {p['name']}: {p['description'][:150]}..." for p in best_projects
    )

    if api_key and _HAS_ANTHROPIC:
        return _ai_cover_letter(job, project_bullets, api_key)
    else:
        return _template_cover_letter(job, best_projects)


def _ai_cover_letter(job: dict, project_bullets: str, api_key: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Write a cover letter for a software engineering internship. Follow these rules strictly:

- Do not use em-dashes or colons
- Do not overuse adjectives or adverbs — cut them unless they add real information
- Vary sentence structure and length throughout
- No filler openers like "I am writing to express my interest" or "I am excited to apply"
- Sound like a real person, not a template
- 3 short paragraphs, under 250 words total
- Paragraph 1: Name the company and role directly, give one specific reason you want this particular company
- Paragraph 2: Reference 2 projects by name, tie specific technical decisions to what the role needs
- Paragraph 3: Short confident close with availability — no flattery
- Do not include addresses or formal letter headers, just the body text

Job: {job.get('title', 'Software Engineer Intern')} at {job.get('company', 'the company')}
Job description: {job.get('description', '')[:600]}

Applicant:
Name: {PROFILE['name']}
Skills: {', '.join(list(PROFILE['skills']['languages']) + list(PROFILE['skills']['frameworks'])[:5])}
Relevant projects:
{project_bullets}
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _template_cover_letter(job: dict, projects: list[dict]) -> str:
    company = job.get("company", "your company")
    title = job.get("title", "Software Engineering Intern")
    p1 = projects[0] if projects else None
    p2 = projects[1] if len(projects) > 1 else None

    body = f"""Hi {company} team,

I'm a software engineering student applying for the {title} role. I build real products — full-stack SaaS platforms, native macOS apps, and Python automation systems — and I'm looking for an internship where I can contribute immediately.

"""
    if p1:
        body += (
            f"Most recently, I built {p1['name']} — {p1['description'][:200]}. "
            f"Key highlights: {', '.join(p1['highlights'][:2])}. "
        )
    if p2:
        body += (
            f"I also built {p2['name']}, a project where I {p2['highlights'][0].lower()}. "
        )
    body += f"""

I'm available immediately and can work full-time. I'd love to bring this kind of initiative to {company}.

Thanks for considering me,
{PROFILE['name']}"""
    return body
