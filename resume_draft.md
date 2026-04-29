# AMANUEL ABU
aabu@sfsu.edu | (669) 292-8473 | linkedin.com/in/amanuelabu | github.com/amanuel2x | San Francisco, CA

---

## EDUCATION

**San Francisco State University** | San Francisco, CA
B.S. Computer Science, Engineering Concentration | Expected May 2026

---

## TECHNICAL SKILLS

**Languages** | Python, TypeScript, JavaScript, Java, SQL, HTML, CSS
**Frameworks** | React, FastAPI, Node.js, Tailwind CSS
**Databases and Infrastructure** | PostgreSQL, Supabase, Redis, SQLite, Cloudflare, Railway
**Tools** | Git, Docker, REST APIs, Webhooks, OAuth 2.0, Stripe API, Meta Ads API

---

## EXPERIENCE

**Freelance Software Developer** | San Francisco, CA | 2023 – Present
*Payment and Campaign Attribution Integrations*

- Designed and shipped call tracking systems for 3+ marketing companies, routing inbound call events through webhook pipelines into Stripe and other payment processors
- Eliminated manual campaign reporting by building attribution pipelines that tied each phone call to its source ad in real time, giving clients immediate visibility into which campaigns generated revenue
- Wrote and maintained production webhook handlers running across multiple simultaneous client accounts with no shared infrastructure
- Cut client onboarding time from several days of manual setup to under two hours through reusable integration tooling

**Whizara | Coding and Robotics Instructor** | San Francisco, CA | Jan 2025 – Jun 2025

- Taught Python programming and software design fundamentals to students across multiple class levels
- Designed and led robotics projects that introduced debugging workflows, iteration, and version control in a hands-on environment
- Tracked individual student progress and adjusted lesson pacing to close comprehension gaps before they compounded

**SeaWeed | Advertising and Media Management Intern** | San Francisco, CA | Feb 2023 – Jun 2023

- Managed paid digital ad campaigns and produced content across social and web channels
- Introduced advertising strategies that drove measurable increases in customer engagement and in-store foot traffic
- Reported campaign performance directly to business leadership and adjusted spend based on weekly results

---

## PROJECTS

**Marketing Agency Verification Platform** | TypeScript, React, PostgreSQL, Supabase, Stripe | 2023

Built a full-stack web platform where marketing agencies submit payment processor credentials to verify their monthly revenue. Verified agencies are ranked on a live leaderboard with reviews, ratings, and embeddable trust badges.

- Designed a payment abstraction layer that connects to Stripe and Whop through a shared factory interface, so adding a new processor requires no database or API changes
- Enforced data isolation at the database level using Supabase Row-Level Security across 8 tables, removing the need for application-level access checks
- Built a reconciliation system that cross-references transaction histories from multiple payment sources to detect and reject inflated revenue claims
- Shipped a re-engagement email system using Supabase scheduled functions that surfaces inactive accounts and pulls them back to the platform

**Enigma Machine Emulator** | Java | 2022

Implemented a working encryption system modeled on the WWII Enigma machine from scratch. No libraries handled the cipher logic — the plugboard substitution, rotor stepping, and reflector mappings were all written by hand.

- Built each mechanical component as its own class and wired them together through a shared cipher pipeline, keeping the encryption logic modular and independently testable
- Implemented accurate rotor advancement including double-stepping behavior, which most simplified versions of this project omit
- Wrote test cases that validated output against known Enigma message pairs from declassified WWII records

---

## COURSEWORK

Data Structures, Machine Learning, Computer Architecture (x86), Algorithm Design, Full-Stack Web Development, Software Engineering Practices
