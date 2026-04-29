"""Generates Amanuel_Abu_Resume.pdf matching the Berkeley template style."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from pathlib import Path

OUTPUT = Path(__file__).parent / "Amanuel_Abu_Resume.pdf"

BLACK = colors.HexColor("#000000")
GRAY = colors.HexColor("#333333")

def make_styles():
    return {
        "name": ParagraphStyle("name",
            fontName="Times-Bold", fontSize=12, leading=15,
            alignment=1, textColor=BLACK, spaceAfter=1),

        "contact": ParagraphStyle("contact",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            alignment=1, textColor=BLACK, spaceAfter=6),

        "section": ParagraphStyle("section",
            fontName="Times-Bold", fontSize=10.5, leading=13,
            textColor=BLACK, spaceBefore=6, spaceAfter=1),

        "org_bold": ParagraphStyle("org_bold",
            fontName="Times-Bold", fontSize=10.5, leading=13,
            textColor=BLACK),

        "role_line": ParagraphStyle("role_line",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            textColor=BLACK, spaceAfter=1),

        "label_bold": ParagraphStyle("label_bold",
            fontName="Times-Bold", fontSize=10.5, leading=13,
            textColor=BLACK),

        "body": ParagraphStyle("body",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            textColor=BLACK, spaceAfter=1),

        "bullet": ParagraphStyle("bullet",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            textColor=BLACK, leftIndent=12, firstLineIndent=0,
            spaceAfter=1),

        "project": ParagraphStyle("project",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            textColor=BLACK, spaceAfter=5),

        "keywords": ParagraphStyle("keywords",
            fontName="Times-Roman", fontSize=10.5, leading=13,
            textColor=BLACK, spaceAfter=0),
    }


def build():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=0.55*inch, rightMargin=0.55*inch,
        topMargin=0.45*inch, bottomMargin=0.45*inch,
    )

    s = make_styles()
    story = []

    # Header
    story.append(Paragraph("Amanuel Abu", s["name"]))
    story.append(Paragraph(
        "aabu@sfsu.edu | (669) 292-8473 | linkedin.com/in/amanuelabu | github.com/amanuel2x",
        s["contact"]
    ))

    # EDUCATION
    story.append(Paragraph("EDUCATION:", s["section"]))
    story.append(Paragraph("San Francisco State University, San Francisco, CA", s["org_bold"]))
    story.append(Paragraph("<b>Major</b>: B.S. Computer Science, Engineering Concentration", s["body"]))
    story.append(Paragraph("<b>Expected Graduation</b>: May 2026", s["body"]))
    story.append(Paragraph(
        "<b>Relevant Coursework</b>: Gained experience in Python and Java programming, focusing on "
        "problem-solving, object-oriented design, and algorithmic efficiency. Built foundational "
        "knowledge in data structures, machine learning models, and low-level computer architecture "
        "(x86). Developed full-stack web applications using modern front-end and back-end technologies. "
        "Applied software engineering practices including version control, Agile methodologies, and "
        "collaborative development workflows.",
        s["body"]
    ))
    story.append(Paragraph(
        "<b>Technical Skills</b>: Python, TypeScript, JavaScript, Java, SQL, HTML, CSS | "
        "React, FastAPI, Node.js, Tailwind CSS | PostgreSQL, Supabase, Redis, Cloudflare | "
        "Git, Docker, REST APIs, OAuth 2.0, Stripe API",
        s["body"]
    ))

    story.append(Spacer(1, 3))

    # EXPERIENCE
    story.append(Paragraph("EXPERIENCE:", s["section"]))

    story.append(Paragraph("<b>Freelance Software Developer</b> \u2013 Payment and Campaign Attribution Integrations", s["org_bold"]))
    story.append(Paragraph("San Francisco, CA | 2023 \u2013 Present", s["role_line"]))
    story.append(Paragraph("* Designed and shipped call tracking systems for 3+ marketing companies, routing inbound call events through webhook pipelines into Stripe and other payment processors", s["bullet"]))
    story.append(Paragraph("* Eliminated manual campaign reporting by building attribution pipelines that tied each phone call to its source ad in real time, giving clients immediate visibility into which campaigns generated revenue", s["bullet"]))
    story.append(Paragraph("* Cut client onboarding time from several days of manual setup to under two hours through reusable integration tooling", s["bullet"]))

    story.append(Spacer(1, 3))

    story.append(Paragraph("<b>Whizara</b> \u2013 Coding/Robotics Instructor", s["org_bold"]))
    story.append(Paragraph("San Francisco, CA | Jan 2025 \u2013 Jun 2025", s["role_line"]))
    story.append(Paragraph("* Taught Python programming and software design fundamentals to students across multiple class levels", s["bullet"]))
    story.append(Paragraph("* Designed and led robotics projects that introduced debugging workflows, iteration, and version control in a hands-on environment", s["bullet"]))
    story.append(Paragraph("* Tracked individual student progress and adjusted lesson pacing to close comprehension gaps before they compounded", s["bullet"]))

    story.append(Spacer(1, 3))

    story.append(Paragraph("<b>SeaWeed</b> \u2013 Advertising & Media Management Intern", s["org_bold"]))
    story.append(Paragraph("San Francisco, CA | Feb 2023 \u2013 Jun 2023", s["role_line"]))
    story.append(Paragraph("* Managed paid digital ad campaigns and produced content across social and web channels", s["bullet"]))
    story.append(Paragraph("* Introduced advertising strategies that drove measurable increases in customer engagement and in-store foot traffic", s["bullet"]))
    story.append(Paragraph("* Reported campaign performance directly to business leadership and adjusted spend based on weekly results", s["bullet"]))

    story.append(Spacer(1, 3))

    # PROJECTS
    story.append(Paragraph("PROJECTS:", s["section"]))

    story.append(Paragraph(
        "<b>Marketing Agency Verification Platform (2024)</b> - Built a full-stack verification platform "
        "for marketing agencies using TypeScript, React, PostgreSQL, and Supabase. Designed a payment "
        "abstraction layer connecting Stripe and Whop through a shared factory interface. Enforced data "
        "isolation at the database level using Supabase Row-Level Security across 8 tables. Built a "
        "reconciliation system that cross-references transaction histories to detect and reject inflated "
        "revenue claims.",
        s["project"]
    ))

    story.append(Paragraph(
        "<b>Enigma Machine (2022)</b> - Built a rotor-based encryption system emulating the WWII Enigma "
        "machine using Java. Implemented plugboard, reflector, and rotor logic with accurate "
        "double-stepping behavior modeled on declassified specifications. Validated output against known "
        "historical message pairs.",
        s["project"]
    ))

    # Keywords
    story.append(Paragraph(
        "<b>Keywords</b>: Python, TypeScript, JavaScript, React, FastAPI, Node.js, PostgreSQL, Supabase, "
        "Stripe API, REST API, OAuth 2.0, Git, Docker, Software Engineering Intern, Full-Stack Development, "
        "Object-Oriented Programming, Agile, Data Structures, Algorithms, Web Development, SQL",
        s["keywords"]
    ))

    doc.build(story)
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    build()
