# The Bridge of Hope Foundation — backend

FastAPI (Python 3.12) + async SQLAlchemy 2.x + Alembic, backed by Neon Postgres.
See `CONTENT-TODO.md` for every real-world fact still needed before this can go live,
and `../files/PROMPT.md` for the full build spec this repo follows.

## Status

Phases 1–2 (scaffold, schema/migrations/seed) and the donation/subscription/webhook/
ledger/manage-cancel flow are complete and tested against the live linked Neon
database, running through an in-house **test payment rail** (`provider: "test"`)
since no live Stripe/PayPal/M-Pesa/BTC credentials have been supplied yet. Those four
real providers are implemented to the shape in the spec but stay off
(`*_ENABLED=false`) and raise a clear "not configured" error if selected — see
`CONTENT-TODO.md` for exactly which credentials unlock each one.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env        # then fill in DATABASE_URL / DIRECT_DATABASE_URL / SECRET_KEY
```

Local Postgres instead of Neon (`docker-compose up -d`), or point `DATABASE_URL` /
`DIRECT_DATABASE_URL` at the linked Neon branch — this repo already has `.neon` /
`neon.ts` set up (`neon link`, `neon deploy`) against the project's `production` branch.

## Migrations

```bash
python -m alembic upgrade head            # apply
python -m alembic revision --autogenerate -m "..."   # after changing app/models/*
```

Alembic needs the **direct** (non-pooled) URL — see `DATABASE_URL_ALEMBIC` in `.env`.
The app itself uses the **pooled** URL (`DATABASE_URL`) — Neon scales to zero, so
`app/db.py` retries the first connection with backoff to ride out a cold start.

## Seed data

```bash
python -m scripts.seed
```

Creates a test admin account and ~8 test donors (all `@yopmail.com` — check inboxes at
https://yopmail.com, no real email is ever sent to them), each with a subscription and
a handful of past donations. Prints the admin login, TOTP secret, and donor emails on
completion — re-run to regenerate the admin password hash; donors/posts are idempotent
on email/slug.

## Running

```bash
uvicorn app.main:app --reload
```

`GET /api/v1/health` — liveness/DB check. Interactive docs at `/docs` (FastAPI default).

## Tests

```bash
pytest
```

18 tests: webhook signature verification (valid + 3 invalid shapes), webhook-event and
donation idempotency (same id delivered twice → one row, run against the live linked
DB), M-Pesa phone normalisation across all four accepted input formats, manage-token
sign/verify/tamper/wrong-secret, and the health check.

## Admin

Session-cookie auth, argon2 password hashing, **mandatory TOTP**, and a per-IP+email
rate limit on `/api/v1/admin/login` (in-memory — fine for one Render instance; swap for
a shared store if this ever scales out). `python -m scripts.seed` prints a base32 TOTP
secret — add it to any authenticator app (Google Authenticator, Authy, etc.) to get
6-digit codes for login.

## Deploy (Render)

`render.yaml` defines a Docker web service. The Dockerfile runs `alembic upgrade head`
before starting uvicorn, so migrations apply automatically on deploy. Set the `sync:
false` env vars in the Render dashboard (never commit real values — `.env` is
git-ignored from the first commit, see `.env.example` for the full list and comments).

## Where credentials come from

See `CONTENT-TODO.md` for the full list per provider. In short: Stripe/PayPal
dashboards issue API keys; Safaricom's Daraja portal issues M-Pesa consumer
key/secret + shortcode/passkey; a BTCPay Server instance (or OpenNode/Coinbase
Commerce account) issues the BTC API key; Google Workspace issues SMTP
credentials for the sending domain (add SPF/DKIM/DMARC records there too, or
receipts land in spam).
