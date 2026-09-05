# Next.js Dashboard — Phase 11 Report

**Adds:** `frontend/` (full Next.js/React/TypeScript app), CORS +
2 new endpoints on the FastAPI backend (`src/api/main.py`), Postgres
persistence wired into `/score`

**Tech stack decision:** the original spec called for Streamlit. That
was deliberately changed this phase — Streamlit can't deploy to
Vercel, and deploying to Vercel was an explicit goal stated earlier in
this project. Next.js is Vercel's own framework, so this gets a
first-class deployment path instead of needing a workaround.

---

## 0. Sandbox Constraints — Different Shape This Time

Node.js and npm **are** installed in this sandbox (`node v22.22.2`,
`npm 10.9.7`) — a first for this project's infrastructure phases. What's
still missing is **network access to the npm registry**, so
`npm install` cannot actually run here, which means:

- No way to install `next`, `react`, `tailwindcss`, etc.
- No way to run `npm run dev` or `npm run build` to verify the app
  actually compiles and renders correctly
- No way to run TypeScript's own compiler to check for type errors

So, same honesty pattern as Kafka/Redis/Postgres: **this code is
written carefully and correctly against well-established, standard
Next.js/React/Tailwind patterns, but it has not been executed or
visually verified in this sandbox.** One real mistake was caught and
fixed during writing (see Section 3) — a reminder that "written
carefully" and "verified" are genuinely different things, which is
exactly why this distinction is called out explicitly throughout this
project rather than glossed over.

**What you should do first, before trusting this further:** run
`npm run dev` locally and actually look at it. This is the most
"visual" deliverable in the whole project, and the one where a subtle
rendering bug (spacing, an unreadable color combination, a broken
layout on mobile) would be easiest to miss without eyes on it.

## 1. Design Approach

The brief here is a fraud-ops monitoring console — something a fraud
analyst would watch to review live risk — not a marketing dashboard.
That grounded the actual design choices (see the design plan discussed
before building, not repeated here): a dark charcoal-navy console
(`#0F1419`) rather than a generic light SaaS-card layout, IBM Plex Sans
paired with IBM Plex Mono for every number (genuinely functional for
scanning tabular financial data, not decorative), and the four risk
tiers (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) as the *only* saturated color
in the interface — carrying real semantic meaning from the spec's
Section 6, not applied decoratively.

Deliberately avoided: rounded shadow-card kits, a generic donut chart
(used a functional segmented risk-composition bar instead), and
decorative motion (the only live element is the polling refresh
itself).

## 2. What's Actually Built

- **`app/page.tsx`** — the dashboard: 4 summary metric cards
  (decisions scored, allowed, flagged for review, blocked), a
  segmented risk-distribution bar, a live "score a transaction" form,
  and a recent-decisions feed — polling the backend every 5 seconds
- **`components/ScoreTransactionForm.tsx`** — lets you submit a test
  transaction from the browser and see the real scoring pipeline's
  decision immediately, with input validation (empty fields, invalid
  amount) before it will submit
- **`lib/api.ts`** — a small typed client for the three backend
  endpoints, reading the backend's URL from `NEXT_PUBLIC_API_URL` so
  the same code works against `localhost` in development and your
  deployed backend once hosted

## 3. A Real Bug Caught During Writing (Worth Reading)

While writing `TransactionFeed.tsx`, I used a Tailwind class pattern
(`border-l-{customColor}` for a colored left-accent strip per risk
tier) and then, on self-review, second-guessed whether Tailwind
actually generates directional border-color utilities for custom
theme colors — briefly "fixed" it to plain `border-{color}` classes,
which would have been a real regression (it would have recolored the
row's bottom divider too, not just the left accent strip). Checked
this again against what I know is Tailwind's actual, documented
behavior (directional border-color utilities — `border-l-`, `border-t-`,
etc. — are a standard, real feature) and reverted to the original,
correct version.

This is flagged here rather than quietly fixed and forgotten, because
it's a good example of exactly the kind of subtle mistake that's easy
to make confidently and hard to catch without actually running the
code — which is precisely why "run `npm run dev` and look at it" is
the real next step, not optional polish.

## 4. Backend Changes Required

The dashboard needs data the API didn't expose before this phase:

- **CORS** (`CORSMiddleware`) — without this, a browser would block
  every request from the Vercel-hosted frontend to the FastAPI
  backend, since they're different origins. `allow_origins=["*"]` is
  set for development convenience; restrict this to your actual
  frontend's URL before treating this as production-ready.
- **`GET /api/decisions/recent`** and **`GET /api/decisions/stats`** —
  both backed by `PostgresDecisionRepository` (Phase 10)
- **`/score` now persists its result** — a transaction scored manually
  from the dashboard's form immediately appears in the recent-decisions
  feed, since it's saved the same way the Kafka consumer's `--postgres`
  flag saves streamed decisions

If Postgres isn't reachable when the API starts, scoring still works,
but the two new dashboard endpoints return a 503 rather than crashing
the whole API — a deliberate choice so a dashboard/database problem
doesn't take down actual fraud scoring.

## 5. Setup & Local Development

```bash
cd frontend
npm install
cp .env.local.example .env.local
# edit .env.local if your backend isn't on http://127.0.0.1:8000
npm run dev
```

Visit `http://localhost:3000`. Your FastAPI backend needs to be
running separately (`uvicorn src.api.main:app --reload`, from the
project root, not inside `frontend/`), with Postgres reachable, for
the dashboard to show real data.

## 6. Deploying to Vercel

1. Push this repo to GitHub (already done)
2. Go to [vercel.com](https://vercel.com), import the repository
3. **Important:** set the project's **Root Directory** to `frontend` —
   Vercel needs to know the Next.js app isn't at the repo root, since
   this is a monorepo alongside the Python backend
4. Add an environment variable: `NEXT_PUBLIC_API_URL` set to your
   deployed backend's URL (see Phase 7's report — Render/Railway/Fly.io
   recommended, not Vercel, for the Python backend itself)
5. Deploy

## 7. Scope Note

This phase makes the dashboard real and gives it a genuine deployment
path. It does not yet: containerize the whole stack for one-command
local startup (Phase 12), or complete final end-to-end testing and
polish across every phase (Phase 13, the last one).
