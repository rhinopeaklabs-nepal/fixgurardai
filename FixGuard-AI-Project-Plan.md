# FixGuard AI — Complete Project Plan

**Author:** contactmdarsalan@gmail.com
**Date:** August 31, 2026
**Project:** FixGuard AI — Pre-Flight QA & Credit-Protection Platform for Hostinger AI Builder
**Hackathon:** Hostinger Challenge (21-Day Build Cycle: Sep 3 – Sep 23, 2026)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Account & Access Setup](#2-account--access-setup)
3. [Tech Stack & Infrastructure](#3-tech-stack--infrastructure)
4. [Architecture Overview](#4-architecture-overview)
5. [21-Day Sprint Plan](#5-21-day-sprint-plan)
6. [Daily Task Breakdown](#6-daily-task-breakdown)
7. [Module Ownership & Dependencies](#7-module-ownership--dependencies)
8. [API Endpoints Checklist](#8-api-endpoints-checklist)
9. [Database Schema Checklist](#9-database-schema-checklist)
10. [Testing Strategy](#10-testing-strategy)
11. [Risk Register & Mitigations](#11-risk-register--mitigations)
12. [Demo & Pitch Preparation](#12-demo--pitch-preparation)
13. [Success Criteria](#13-success-criteria)
14. [Daily Standup Template](#14-daily-standup-template)

---

## 1. Project Overview

### What is FixGuard AI?
FixGuard AI is a **pre-flight testing and prompt-refining safety net** that sits alongside Hostinger AI Builder. It does NOT replace AI Builder — it protects users from wasting credits and shipping broken sites.

### The Three Core Problems We Solve

| # | Problem | Who | Impact |
|---|---------|-----|--------|
| 1 | **Credit Exhaustion & Code Regressions** | Sarah (Site Builder) | Simple tweaks burn 10-50+ credits; AI breaks existing CSS/JS |
| 2 | **Silent Backend & Form Failures** | Marcus (Freelancer) | Forms show "Success" but no email arrives |
| 3 | **Client Handover & Configuration Friction** | Priya (Developer) | React Router loops, geo-blocks, no pre-delivery QA |

### The Four Modules

```
Module 1: Surgical Prompt Studio (Credit Shield)
  └─ Generates scoped, single-purpose prompts that prevent site-wide regressions

Module 2: Synthetic Form & SMTP Tester
  └─ Headless form submission with temporary inbox verification

Module 3: Router & Geo-Health Auditor
  └─ Navigation loop detection, console error capture, multi-region geo-ping

Module 4: Client Handoff Verification Report
  └─ 0-100 Health Score + Branded PDF + Shareable Link
```

### 4-Product Hostinger Integration

| Product | Role | What It Hosts |
|---------|------|---------------|
| **AI Builder** | Marketing & Lead Funnel | Landing page, intake form, feature demos |
| **Web Hosting** | User Dashboard | React SPA, audit reports, shareable links |
| **VPS** | Core Engine | Docker: FastAPI, Playwright, MailHog, Redis, DB, NGINX |
| **AI Agents** | Intelligence Layer | Log Parser, Prompt Generator, Summary Agent |

---

## 2. Account & Access Setup

### Accounts Required

| Service | Account | Purpose | Status |
|---------|---------|---------|--------|
| Hostinger AI Builder | contactmdarsalan@gmail.com | Marketing site | ⬜ Pending |
| Hostinger Web Hosting | contactmdarsalan@gmail.com | Dashboard hosting | ⬜ Pending |
| Hostinger VPS | contactmdarsalan@gmail.com | Docker backend | ⬜ Pending |
| Hostinger AI Agents | contactmdarsalan@gmail.com | AI API access | ⬜ Pending |
| GitHub | contactmdarsalan@gmail.com | Source code repo | ⬜ Pending |
| Discord (Hostinger) | contactmdarsalan@gmail.com | Community access | ⬜ Pending |

### VPS Specs (Recommended)

```
OS:           Ubuntu 22.04 LTS
CPU:          4 vCPU (minimum)
RAM:          8 GB (minimum for Playwright workers)
Storage:      40 GB SSD
Bandwidth:    Unlimited
Docker:       Docker Engine + Docker Compose
```

### Environment Variables to Configure

```bash
# Backend (.env)
DATABASE_URL=sqlite:///./fixguard.db
REDIS_URL=redis://redis:6379
AI_AGENTS_API_KEY=your_hostinger_ai_agents_key
MAILHOG_HOST=mailhog
MAILHOG_PORT=1025
API_KEY_HMAC_SECRET=your_hmac_secret
CORS_ORIGINS=https://your-web-hosting-domain.com
PDF_RENDER_URL=http://playwright:3000/render-pdf

# Frontend (.env)
VITE_API_BASE_URL=https://api.fixguard.ai/api/v1
VITE_WS_URL=wss://api.fixguard.ai/ws
```

---

## 3. Tech Stack & Infrastructure

### Technology Matrix

| Layer | Technology | Hostinger Target | Why |
|-------|-----------|-----------------|-----|
| Marketing Site | Hostinger AI Builder | AI Builder | Requirement |
| Frontend | React + Vite + Tailwind CSS | Web Hosting | Fast, modern SPA |
| Backend API | Python FastAPI | VPS (Docker) | Async, high-performance |
| Automation | Playwright (Chromium) | VPS (Docker) | Headless browser testing |
| Task Queue | Redis + BullMQ | VPS (Docker) | Async job processing |
| Database | SQLite (MVP) | VPS (Docker) | Simple, zero-config |
| SMTP Interceptor | MailHog | VPS (Docker) | Email capture + headers |
| Reverse Proxy | NGINX | VPS | TLS, rate limiting |
| AI Processing | Hostinger AI Agents API | AI Agents | Intelligence layer |
| PDF Generation | Puppeteer | VPS (Docker) | HTML-to-PDF certificates |

### Docker Compose Services

```yaml
services:
  nginx:        # Reverse proxy — ports 80/443 (external)
  api:          # FastAPI gateway — port 8000 (internal)
  playwright:   # Headless Chromium — scales 1-3 replicas
  mailhog:      # SMTP interceptor — ports 1025/8025 (internal)
  redis:        # Task queue — port 6379 (internal)
  db:           # SQLite volume — port 5432 (internal)
```

---

## 4. Architecture Overview

### Data Flow (End-to-End)

```
User submits URL + selects modules
        │
        ▼
AI Builder / Dashboard intake
        │
        ▼
FastAPI receives request
        │
        ├─ URL valid & reachable?
        │   ├─ No → Return INVALID_URL / UNREACHABLE
        │   └─ Yes → Enqueue job in Redis
        │
        ├─ Open SSE progress stream
        │
        ├─ Which modules?
        │   ├─ Form → Playwright: form test → MailHog poll → Header verify
        │   ├─ Router → Playwright: route crawl → Loop detect → Console capture
        │   └─ Geo → Multi-region HTTP ping (3 regions)
        │
        ├─ Raw logs collected
        │
        ├─ AI Agent 1: Parse logs to plain English
        │
        ├─ Store results in DB
        │
        ├─ Compute Health Score (0-100)
        │
        ├─ AI Agent 3: Executive summary
        │
        ├─ Generate report + PDF + share link
        │
        └─ SSE: complete event → Dashboard displays report
```

### Component Diagram

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI Gateway                    │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Routers │ │ Auth MW  │ │Rate Limiter│ │ SSE Mgr│ │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ │
│       └───────────┴────────────┴────────────┘       │
│                          │                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Audit    │ │ Prompt   │ │ Form     │ │ Health │ │
│  │ Service  │ │ Service  │ │ Service  │ │ Score  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │             │            │            │      │
│  ┌────┴─────┐ ┌─────┴────┐ ┌────┴─────┐ ┌───┴───┐ │
│  │ Scope    │ │ AI Agent │ │ Playwright│ │  DB   │ │
│  │ Engine   │ │ Client   │ │ Queue    │ │ Repo  │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 5. 21-Day Sprint Plan

### Phase 1: Architecture & VPS Setup (Days 1–4)
**Goal:** Foundation ready, all services running, basic connectivity verified.

### Phase 2: Core Automation Engine (Days 5–11)
**Goal:** All 4 modules functional, end-to-end vertical slice working.

### Phase 3: Polish & Client Reports (Days 12–17)
**Goal:** PDF reports, geo-ping, UI polish, real-site testing.

### Phase 4: Final Testing & Submission (Days 18–21)
**Goal:** All tests pass, pitch video recorded, project submitted.

### Gantt Chart Overview

```
Sep 03 ──── Phase 1: Setup ──────────────── Sep 06
Sep 07 ──── Phase 2: Core Engine ────────── Sep 13
Sep 14 ──── Phase 3: Polish ─────────────── Sep 19
Sep 20 ──── Phase 4: Submission ─────────── Sep 23
```

---

## 6. Daily Task Breakdown

### Phase 1: Architecture & VPS Setup (Days 1–4)

#### Day 1 — Sep 3 (Wed): Infrastructure
| # | Task | Time | Done |
|---|------|------|------|
| 1.1 | Register for Hostinger challenge on Discord | 30min | ⬜ |
| 1.2 | Create GitHub repo: `fixguard-ai` | 30min | ⬜ |
| 1.3 | Provision Hostinger VPS (Ubuntu 22.04, 4 vCPU, 8GB RAM) | 1hr | ⬜ |
| 1.4 | Install Docker Engine + Docker Compose | 1hr | ⬜ |
| 1.5 | Install NGINX, Node.js 20, Python 3.11 | 1hr | ⬜ |
| 1.6 | Configure firewall (only 80/443 exposed) | 30min | ⬜ |
| 1.7 | Set up SSH key-based authentication | 15min | ⬜ |
| 1.8 | Verify VPS accessibility from browser | 15min | ⬜ |

**Deliverable:** VPS accessible, Docker running, repo created.

---

#### Day 2 — Sep 4 (Thu): AI Builder Marketing Site
| # | Task | Time | Done |
|---|------|------|------|
| 2.1 | Log into Hostinger AI Builder with contactmdarsalan@gmail.com | 15min | ⬜ |
| 2.2 | Create new site project "FixGuard AI" | 30min | ⬜ |
| 2.3 | Build landing page hero: "Stop Wasting AI Builder Credits" | 1hr | ⬜ |
| 2.4 | Add value proposition section (3 pain points → 3 solutions) | 1hr | ⬜ |
| 2.5 | Create lead capture form (name, email, site URL) | 1hr | ⬜ |
| 2.6 | Add quick-audit intake form (enter URL → get preview) | 1hr | ⬜ |
| 2.7 | Add interactive feature demos (3 module cards) | 1hr | ⬜ |
| 2.8 | Configure form to send leads to dashboard intake endpoint | 30min | ⬜ |

**Deliverable:** AI Builder marketing page live with intake form.

---

#### Day 3 — Sep 5 (Fri): Database & API Skeleton
| # | Task | Time | Done |
|---|------|------|------|
| 3.1 | Design DB schema (all 7 tables from SRS) | 1hr | ⬜ |
| 3.2 | Create FastAPI project structure (routers/, services/, models/, workers/) | 30min | ⬜ |
| 3.3 | Write SQLAlchemy models for all 7 tables | 2hr | ⬜ |
| 3.4 | Create database initialization scripts | 30min | ⬜ |
| 3.5 | Implement API key generation (UUID v4 + HMAC-SHA256) | 1hr | ⬜ |
| 3.6 | Write basic health check endpoint: GET /api/v1/health | 15min | ⬜ |
| 3.7 | Create Docker Compose file with all 6 services | 1hr | ⬜ |
| 3.8 | Test docker-compose up — verify all services start | 30min | ⬜ |

**Deliverable:** DB schema implemented, FastAPI skeleton with model definitions.

---

#### Day 4 — Sep 6 (Sat): Dashboard Shell
| # | Task | Time | Done |
|---|------|------|------|
| 4.1 | Initialize React/Vite + Tailwind project | 30min | ⬜ |
| 4.2 | Build dashboard shell with sidebar navigation | 1hr | ⬜ |
| 4.3 | Create pages: Home, Audits, Prompts, Reports, Settings | 1hr | ⬜ |
| 4.4 | Configure CORS on FastAPI for Web Hosting domain | 30min | ⬜ |
| 4.5 | Connect dashboard to VPS API health check | 30min | ⬜ |
| 4.6 | Build API client service layer (fetch wrappers) | 1hr | ⬜ |
| 4.7 | Implement API key input on Settings page | 30min | ⬜ |
| 4.8 | Test cross-origin requests (dashboard → VPS) | 30min | ⬜ |
| 4.9 | Deploy static build to Web Hosting | 30min | ⬜ |

**Deliverable:** Web Hosting dashboard shell live, API connectivity verified.

---

### Phase 2: Core Automation Engine (Days 5–11)

#### Day 5 — Sep 7 (Sun): Playwright Console Crawler
| # | Task | Time | Done |
|---|------|------|------|
| 5.1 | Install Playwright in Docker container | 1hr | ⬜ |
| 5.2 | Build Chromium launcher with stealth plugin | 1hr | ⬜ |
| 5.3 | Implement console error listener (console.error, console.warn) | 1hr | ⬜ |
| 5.4 | Build navigation route tracker (record all URL changes) | 1hr | ⬜ |
| 5.5 | Detect "Throttling navigation to prevent browser hang" | 30min | ⬜ |
| 5.6 | Implement rapid navigation loop detection (≥5 in 3s) | 1hr | ⬜ |
| 5.7 | Capture console errors with source URL and line number | 30min | ⬜ |
| 5.8 | Test against real site with known console errors | 30min | ⬜ |

**Deliverable:** Playwright worker captures console + route data from target URL.

---

#### Day 6 — Sep 8 (Mon): Synthetic Form Worker
| # | Task | Time | Done |
|---|------|------|------|
| 6.1 | Build DOM field parser (detect input types) | 1.5hr | ⬜ |
| 6.2 | Implement type-aware test payload generator | 1hr | ⬜ |
| 6.3 | Build form filler (fill fields with test data) | 1hr | ⬜ |
| 6.4 | Implement submit button click simulation | 30min | ⬜ |
| 6.5 | Intercept outbound network requests during submission | 1hr | ⬜ |
| 6.6 | Capture HTTP response status + body | 30min | ⬜ |
| 6.7 | Capture client-side JS errors during submission | 30min | ⬜ |
| 6.8 | Test against real contact form (create test site) | 1hr | ⬜ |

**Deliverable:** Form submission worker functional against test sites.

---

#### Day 7 — Sep 9 (Tue): MailHog SMTP Interceptor
| # | Task | Time | Done |
|---|------|------|------|
| 7.1 | Deploy MailHog container in Docker Compose | 30min | ⬜ |
| 7.2 | Build temporary inbox generation API | 1hr | ⬜ |
| 7.3 | Implement email polling logic (30s window) | 1hr | ⬜ |
| 7.4 | Parse email headers: Reply-To, From | 1hr | ⬜ |
| 7.5 | Implement DKIM signature validation | 1hr | ⬜ |
| 7.6 | Implement SPF record checking | 1hr | ⬜ |
| 7.7 | Build silent failure detection (success shown, no request made) | 1hr | ⬜ |
| 7.8 | Test with form that has missing Reply-To header | 30min | ⬜ |

**Deliverable:** SMTP interceptor captures and verifies test emails.

---

#### Day 8 — Sep 10 (Wed): AI Agent 1 — Log Parser
| # | Task | Time | Done |
|---|------|------|------|
| 8.1 | Connect to Hostinger AI Agents API | 1hr | ⬜ |
| 8.2 | Write system prompt for Agent 1 (Log Parser) | 1hr | ⬜ |
| 8.3 | Test with sample console logs (5 scenarios) | 1hr | ⬜ |
| 8.4 | Implement fallback to static templates on agent error | 30min | ⬜ |
| 8.5 | Log agent calls with input/output and latency | 30min | ⬜ |
| 8.6 | Test with real browser console logs | 1hr | ⬜ |

**Deliverable:** AI Agent 1 transforms raw logs into readable explanations.

---

#### Day 9 — Sep 11 (Thu): AI Agent 2 — Prompt Generator
| # | Task | Time | Done |
|---|------|------|------|
| 9.1 | Build AST/DOM scoping engine | 2hr | ⬜ |
| 9.2 | Write guardrail injection prompts | 1hr | ⬜ |
| 9.3 | Test with 5 input types: color, layout, form, text, font | 1.5hr | ⬜ |
| 9.4 | Implement "DO NOT modify" clause generation | 1hr | ⬜ |
| 9.5 | Calculate tokens_saved_estimate (naive vs surgical) | 30min | ⬜ |
| 9.6 | Build differential code preview renderer | 1hr | ⬜ |

**Deliverable:** AI Agent 2 produces scoped surgical prompts with DO NOT clauses.

---

#### Day 10 — Sep 12 (Fri): Dashboard + SSE Integration
| # | Task | Time | Done |
|---|------|------|------|
| 10.1 | Build SSE progress stream handler | 1.5hr | ⬜ |
| 10.2 | Create audit progress bar component | 1hr | ⬜ |
| 10.3 | Display form test results (pass/fail per check) | 1hr | ⬜ |
| 10.4 | Display router audit results (route map, loop warnings) | 1hr | ⬜ |
| 10.5 | Display geo-ping results (3-region status) | 1hr | ⬜ |
| 10.6 | Build surgical prompt generator UI (intent input → prompt output) | 1hr | ⬜ |
| 10.7 | Implement clipboard copy for surgical prompts | 15min | ⬜ |

**Deliverable:** Dashboard shows live audit execution end-to-end.

---

#### Day 11 — Sep 13 (Sat): E2E Integration Test
| # | Task | Time | Done |
|---|------|------|------|
| 11.1 | End-to-end test: URL → Form Audit → Report | 1.5hr | ⬜ |
| 11.2 | End-to-end test: URL → Router Audit → Report | 1.5hr | ⬜ |
| 11.3 | End-to-end test: URL → Full Audit → Report | 1.5hr | ⬜ |
| 11.4 | End-to-end test: Intent → Surgical Prompt → Copy | 1hr | ⬜ |
| 11.5 | Fix any integration bugs | 2hr | ⬜ |
| 11.6 | Verify full loop completes in < 60s | 30min | ⬜ |
| 11.7 | Document remaining issues | 30min | ⬜ |

**Deliverable:** Full vertical slice working: URL in → audit report out.

---

### Phase 3: Polish & Client Reports (Days 12–17)

#### Day 12 — Sep 14 (Sun): PDF Report Generator
| # | Task | Time | Done |
|---|------|------|------|
| 12.1 | Build health score calculation algorithm (weighted average) | 1hr | ⬜ |
| 12.2 | Create PDF HTML template with FixGuard branding | 2hr | ⬜ |
| 12.3 | Implement Puppeteer HTML-to-PDF rendering | 1.5hr | ⬜ |
| 12.4 | Add PDF download endpoint: GET /api/v1/reports/:id/pdf | 30min | ⬜ |
| 12.5 | Test PDF generation with sample audit data | 1hr | ⬜ |

**Deliverable:** PDF audit certificate downloadable from dashboard.

---

#### Day 13 — Sep 15 (Mon): Multi-Region Geo-Ping
| # | Task | Time | Done |
|---|------|------|------|
| 13.1 | Set up 3 geo-ping proxy endpoints (US-East, EU-Central, Asia-South) | 1.5hr | ⬜ |
| 13.2 | Implement HTTP GET from each region | 1hr | ⬜ |
| 13.3 | Record status code, latency, SSL validity, DNS resolution | 1hr | ⬜ |
| 13.4 | Build geo-block detection (403 in one region, 200 in others) | 1hr | ⬜ |
| 13.5 | Test with site that blocks certain regions | 1hr | ⬜ |

**Deliverable:** Geo-ping returns 3-region results with block detection.

---

#### Day 14 — Sep 16 (Tue): UI/UX Polish
| # | Task | Time | Done |
|---|------|------|------|
| 14.1 | Ensure visual consistency with AI Builder marketing page | 1hr | ⬜ |
| 14.2 | Add skeleton loaders for all async operations | 1hr | ⬜ |
| 14.3 | Add error states for failed operations | 1hr | ⬜ |
| 14.4 | Add empty states (no audits yet, no prompts yet) | 1hr | ⬜ |
| 14.5 | Polish responsive design (mobile, tablet, desktop) | 1.5hr | ⬜ |
| 14.6 | Add shareable audit link UI + copy button | 30min | ⬜ |

**Deliverable:** Dashboard is polished, responsive, and visually consistent.

---

#### Day 15 — Sep 17 (Wed): Architecture Page
| # | Task | Time | Done |
|---|------|------|------|
| 15.1 | Build /architecture page with interactive diagram | 2hr | ⬜ |
| 15.2 | Show all 4 Hostinger products with data flow | 1hr | ⬜ |
| 15.3 | Add live status indicators for each product layer | 1hr | ⬜ |
| 15.4 | Add real-time data flow animation | 1hr | ⬜ |
| 15.5 | Test page renders correctly | 30min | ⬜ |

**Deliverable:** /architecture page live with 4-product integration diagram.

---

#### Day 16 — Sep 18 (Thu): Real-Site Stress Testing
| # | Task | Time | Done |
|---|------|------|------|
| 16.1 | Create 3 test sites with known issues | 1.5hr | ⬜ |
| 16.2 | Request test sites from Discord community | 30min | ⬜ |
| 16.3 | Run 5+ audits against real AI Builder sites | 2hr | ⬜ |
| 16.4 | Document all edge cases found | 1hr | ⬜ |
| 16.5 | Time each audit (verify < 60s target) | 30min | ⬜ |

**Deliverable:** 5+ real-site audits completed, edge cases documented.

---

#### Day 17 — Sep 19 (Fri): Edge Case Fixes + Agent 3
| # | Task | Time | Done |
|---|------|------|------|
| 17.1 | Fix edge cases from Day 16 testing | 2hr | ⬜ |
| 17.2 | Optimize VPS container memory usage | 1hr | ⬜ |
| 17.3 | Implement retry logic for failed audits | 1hr | ⬜ |
| 17.4 | Build Agent 3 (Summary Agent) for executive summaries | 1.5hr | ⬜ |
| 17.5 | Add AI Agent 3 integration to full audit flow | 30min | ⬜ |

**Deliverable:** Edge cases resolved, system stable, summary agent working.

---

### Phase 4: Final Testing & Submission (Days 18–21)

#### Day 18 — Sep 20 (Sat): Final E2E Testing
| # | Task | Time | Done |
|---|------|------|------|
| 18.1 | Run all 12 test scenarios from SRS | 3hr | ⬜ |
| 18.2 | Verify full audit loop < 60s on 5 sites | 2hr | ⬜ |
| 18.3 | Test PDF generation with all score grades | 1hr | ⬜ |
| 18.4 | Test shareable links (create, access, expiry) | 1hr | ⬜ |
| 18.5 | Document any remaining bugs | 1hr | ⬜ |

**Deliverable:** All test scenarios pass, full loop < 60s verified.

---

#### Day 19 — Sep 21 (Sun): Pitch Video Recording
| # | Task | Time | Done |
|---|------|------|------|
| 19.1 | Write pitch video script (2 min) | 1hr | ⬜ |
| 19.2 | Prepare demo: capture Discord screenshots for pain section | 30min | ⬜ |
| 19.3 | Record live audit demo (screen capture) | 1hr | ⬜ |
| 19.4 | Record architecture page walkthrough | 30min | ⬜ |
| 19.5 | Edit video (Pain → Demo → Architecture → Impact) | 2hr | ⬜ |
| 19.6 | Practice pitch 3 times | 30min | ⬜ |

**Deliverable:** 2-minute pitch video recorded and edited.

---

#### Day 20 — Sep 22 (Mon): Documentation
| # | Task | Time | Done |
|---|------|------|------|
| 20.1 | Write README.md with setup instructions | 1hr | ⬜ |
| 20.2 | Document API endpoints (OpenAPI/Swagger) | 1hr | ⬜ |
| 20.3 | Create architecture flowcharts (Mermaid) | 1hr | ⬜ |
| 20.4 | Prepare submission documentation package | 1hr | ⬜ |
| 20.5 | Verify all live links work | 30min | ⬜ |

**Deliverable:** Complete submission documentation package.

---

#### Day 21 — Sep 23 (Tue): Submission
| # | Task | Time | Done |
|---|------|------|------|
| 21.1 | Final review of all deliverables | 1hr | ⬜ |
| 21.2 | Submit project on official platform | 30min | ⬜ |
| 21.3 | Share progress in Hostinger Discord | 30min | ⬜ |
| 21.4 | Monitor for last-minute issues | 1hr | ⬜ |
| 21.5 | Celebrate! 🎉 | — | ⬜ |

**Deliverable:** Project submitted, Discord post shared.

---

## 7. Module Ownership & Dependencies

### Module Dependency Graph

```
Module 1 (Surgical Prompt Studio)
├── Depends on: AI Agent 2 (Prompt Generator)
├── Depends on: AST/DOM Scoping Engine
└── Depends on: Playwright (optional DOM extraction)

Module 2 (Form & SMTP Tester)
├── Depends on: Playwright Worker
├── Depends on: MailHog SMTP Container
└── Depends on: AI Agent 1 (Log Parser)

Module 3 (Router & Geo Auditor)
├── Depends on: Playwright Worker
├── Depends on: Geo-Ping Service (3 regions)
└── Depends on: AI Agent 1 (Log Parser)

Module 4 (Client Handoff Report)
├── Depends on: Health Score Algorithm
├── Depends on: Puppeteer PDF Renderer
├── Depends on: AI Agent 3 (Summary Agent)
└── Depends on: Results from Modules 1-3
```

### Build Order (Critical Path)

```
Week 1: Infrastructure → Playwright → Form Worker → MailHog
Week 2: AI Agents → Dashboard Integration → E2E Test
Week 3: PDF → Geo-Ping → UI Polish → Architecture Page
Week 4: Testing → Video → Documentation → Submission
```

---

## 8. API Endpoints Checklist

| # | Method | Endpoint | Purpose | Status |
|---|--------|----------|---------|--------|
| 1 | POST | /api/v1/audits/start | Start new audit run | ⬜ |
| 2 | GET | /api/v1/audits/:id/status | Poll audit status | ⬜ |
| 3 | GET | /api/v1/audits/:id/stream | SSE progress stream | ⬜ |
| 4 | GET | /api/v1/audits/:id/report | Get full audit report | ⬜ |
| 5 | POST | /api/v1/prompts/surgify | Generate surgical prompt | ⬜ |
| 6 | POST | /api/v1/forms/synthetic-test | Standalone form test | ⬜ |
| 7 | GET | /api/v1/reports/:id/pdf | Download PDF certificate | ⬜ |
| 8 | GET | /api/v1/reports/:id/share | Get shareable report data | ⬜ |
| 9 | GET | /api/v1/prompts/history | Prompt generation history | ⬜ |
| 10 | GET | /api/v1/health | Health check | ⬜ |

---

## 9. Database Schema Checklist

| # | Table | Purpose | Status |
|---|-------|---------|--------|
| 1 | users | User accounts + API keys | ⬜ |
| 2 | projects | Website projects (domain URLs) | ⬜ |
| 3 | audit_runs | Audit execution records | ⬜ |
| 4 | form_test_results | Form/SMTP test results | ⬜ |
| 5 | router_audit_results | Router/console audit results | ⬜ |
| 6 | geo_ping_results | Multi-region ping results | ⬜ |
| 7 | surgical_prompts | Generated prompt history | ⬜ |
| 8 | console_error_logs | Captured console errors | ⬜ |
| 9 | health_scores | Computed health scores | ⬜ |
| 10 | share_links | Public shareable audit links | ⬜ |

---

## 10. Testing Strategy

### Test Scenarios (Must Pass)

| ID | Scenario | Expected Result | Status |
|----|----------|----------------|--------|
| T-01 | Submit valid URL for form audit | Audit completes, form result returned | ⬜ |
| T-02 | Submit unreachable URL | Returns UNREACHABLE_TARGET error | ⬜ |
| T-03 | Form shows success but no HTTP request | Flags silent_failure_detected: true | ⬜ |
| T-04 | Form sends email without Reply-To header | Flags reply_to_valid: false | ⬜ |
| T-05 | Target site has React Router loop | Detects has_navigation_loop: true | ⬜ |
| T-06 | Target site has console errors | Captures errors with source and line | ⬜ |
| T-07 | Geo-ping from Asia-South returns 403 | Flags ip_blocked: true for that region | ⬜ |
| T-08 | Generate surgical prompt for "change button color" | Output scopes to specific selector | ⬜ |
| T-09 | Rate limit: 11th audit in 1 hour | Returns RATE_LIMIT_EXCEEDED | ⬜ |
| T-10 | Full audit completes in < 60s | Health score + PDF generated | ⬜ |
| T-11 | Shareable audit link accessed without auth | Report renders in client-facing mode | ⬜ |
| T-12 | Shareable link accessed after 30 days | Returns 410 Gone | ⬜ |

### Demo Verification Checklist

- [ ] Marketing page on AI Builder loads and intake form submits
- [ ] Dashboard on Web Hosting loads and connects to VPS API
- [ ] Form audit runs against real test site and detects a failure
- [ ] Surgical prompt generator produces a scoped prompt for a live input
- [ ] Router audit catches a "Throttling navigation" console warning
- [ ] Geo-ping returns results from 3 regions
- [ ] PDF certificate downloads successfully
- [ ] Shareable audit link opens in browser
- [ ] /architecture page displays 4-product integration diagram
- [ ] Full end-to-end loop completes in < 60 seconds

---

## 11. Risk Register & Mitigations

| ID | Risk | Prob | Impact | Mitigation | Owner |
|----|------|------|--------|------------|-------|
| R-01 | Playwright crashes on complex SPAs | Med | High | 30s timeout, retry logic, Docker auto-restart. Test 5+ real sites by Day 16 | Owner |
| R-02 | AI Agents API latency/rate limits | Med | Med | Cache common patterns. Fallback to static prompt templates | Owner |
| R-03 | MailHog misses certain SMTP configs | Low | Med | Test 3+ form backends. Fallback: "no email received" (still useful) | Owner |
| R-04 | Geo-ping proxy unavailable | Low | Low | 3 independent proxies. Report "unavailable" for failed regions | Owner |
| R-05 | VPS resource exhaustion | Med | High | Limit 3 concurrent workers. Monitor memory. restart: unless-stopped | Owner |
| R-06 | CORS issues between Web Hosting and VPS | Med | High | Configure CORS on Day 4. Test cross-origin early | Owner |
| R-07 | 60s audit deadline not met | Med | Med | Parallelize modules. Start geo-ping concurrently with Playwright | Owner |
| R-08 | Pitch video exceeds 2 minutes | Low | High | Script by Day 18. Practice 3 times. Demo ≤ 60s | Owner |

---

## 12. Demo & Pitch Preparation

### Pitch Video Script (2 Minutes)

| Time | Section | Content | Visual |
|------|---------|---------|--------|
| 0:00–0:20 | **The Pain** | "These are real Hostinger users losing money and time." | Discord screenshots: burnt credits, broken forms, router loops |
| 0:20–0:50 | **The Solution** | Live demo: paste URL → audit runs → catches broken Reply-To → surgical prompt generated | Screen recording of FixGuard dashboard |
| 0:50–1:30 | **The Architecture** | "AI Builder captures leads. Web Hosting serves the dashboard. VPS runs Playwright and MailHog. AI Agents parse logs and generate prompts." | /architecture page walkthrough |
| 1:30–2:00 | **The Impact** | "FixGuard saves credits, catches silent failures, delivers verified sites. Built by the community, for the community." | Health score + PDF certificate + CTA |

### Competitive Differentiation

| Differentiator | Why It Matters |
|---------------|----------------|
| Community-Sourced Problem | Built from actual Discord pain points judges recognize |
| Credit Protection | No other tool addresses AI Builder credit waste |
| 4-Product Interdependence | Each product fails without the others |
| Surgical Prompt Innovation | Users get a better prompt, not a replacement |

---

## 13. Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| All 4 Hostinger products demonstrably interconnected | Required | ⬜ |
| End-to-end audit loop < 60s for single URL | Target | ⬜ |
| Surgical prompt generator works for 5+ input types | Required | ⬜ |
| Form test detects at least 1 real failure mode | Required | ⬜ |
| Router audit catches "Throttling navigation" warning | Required | ⬜ |
| Client handoff PDF generates with health score | Required | ⬜ |
| /architecture page shows 4-product data flow | Required | ⬜ |
| 2-minute pitch video submitted | Required | ⬜ |

---

## 14. Daily Standup Template

Use this template every morning:

```
📅 Date: [Day X] — [Date]
⏰ Time spent yesterday: [X hours]
✅ Completed yesterday:
  - [Task 1]
  - [Task 2]
🚧 Working on today:
  - [Task 1]
  - [Task 2]
🚫 Blockers:
  - [Any blockers]
📊 Progress: [X]% complete ([X]/21 days)
🎯 Today's goal: [One sentence goal for the day]
```

---

**Document End — FixGuard AI Complete Project Plan**

**Next Steps:**
1. Register for Hostinger challenge on Discord
2. Provision VPS (Day 1)
3. Start building! 🚀
