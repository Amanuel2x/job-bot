"""
Your personal profile — skills, experience, and projects.
Edit this file to keep it current. The bot uses it to match jobs and write cover letters.
"""

PROFILE = {
    "name": "Amanuel Abu",
    "email": "aabu@sfsu.edu",
    "phone": "(669) 292-8473",
    "linkedin": "https://www.linkedin.com/in/amanuelabu",
    "github": "https://github.com/amanuel2x",
    "location": "San Francisco, CA",
    "school": "San Francisco State University",
    "degree": "B.S. Computer Science, Engineering Concentration",
    "graduation": "May 2026",
    "role_target": "Software Engineering Intern",
    "summary": (
        "CS student at SFSU (May 2026) who builds and ships real software — "
        "a full-stack AI SaaS platform, a native macOS app, Python automation bots, "
        "and freelance integrations for marketing clients. Experienced across the full stack: "
        "React, FastAPI, PostgreSQL, Swift, and the Claude API."
    ),

    # Skills — used for job matching
    "skills": {
        "languages": ["Python", "TypeScript", "JavaScript", "Swift", "SQL", "HTML", "CSS"],
        "frameworks": ["React", "FastAPI", "SwiftUI", "Vite", "Tailwind CSS", "Node.js"],
        "databases": ["PostgreSQL", "Supabase", "Redis", "SQLite"],
        "tools": ["Git", "Docker", "Celery", "Selenium", "REST APIs", "Webhooks"],
        "platforms": ["Cloudflare", "Railway", "Supabase", "macOS", "Linux"],
        "ai_ml": ["Claude API", "Anthropic SDK", "prompt engineering", "LLM integration"],
        "other": [
            "multi-tenant architecture",
            "OAuth 2.0",
            "WebSockets",
            "Stripe API",
            "Meta Ads API",
            "Google Ads API",
        ],
    },

    # Projects — described for cover letters and matching
    "projects": [
        {
            "name": "Agency Ranks — Verified Agency Leaderboard",
            "description": (
                "React SPA + Supabase backend for ranking marketing agencies by verified MRR. "
                "Includes multi-provider payment abstraction (Stripe, Whop), RLS-secured database, "
                "weekly digest email engine, and admin moderation panel."
            ),
            "tech": ["TypeScript", "React", "Supabase", "PostgreSQL", "Stripe API"],
            "highlights": [
                "Designed payment provider abstraction supporting Stripe and Whop via factory pattern",
                "Implemented Supabase RLS across 8+ tables for row-level data isolation",
                "Built weekly email digest engine for user re-engagement",
            ],
        },
        {
            "name": "Call Tracking Automation (Freelance)",
            "description": (
                "Built call tracking automation systems integrated with payment processors for marketing companies. "
                "Tracked phone call attribution and connected inbound call events to revenue data in client dashboards."
            ),
            "tech": ["Python", "REST APIs", "Stripe API", "webhooks"],
            "highlights": [
                "Automated attribution of inbound calls to ad campaigns",
                "Integrated call data with payment processors for revenue tracking",
                "Delivered for multiple marketing company clients",
            ],
        },
    ],

    # Job preferences — used to filter and rank job listings
    "preferences": {
        "roles": [
            "Software Engineer Intern",
            "SWE Intern",
            "Software Development Intern",
            "Backend Engineer Intern",
            "Full Stack Engineer Intern",
            "Frontend Engineer Intern",
            "Engineering Intern",
            "Python Developer Intern",
        ],
        "exclude_keywords": [
            "hardware",
            "embedded",
            "FPGA",
            "mechanical",
            "civil",
            "electrical engineer",
            "data entry",
            "QA only",
        ],
        "preferred_keywords": [
            "Python",
            "TypeScript",
            "React",
            "FastAPI",
            "API",
            "full stack",
            "backend",
            "SaaS",
            "startup",
            "AI",
            "machine learning",
            "cloud",
        ],
        "location": "Remote",  # or "New York, NY" etc — "Remote" matches remote-friendly listings
        "min_job_length_weeks": 8,
    },
}
