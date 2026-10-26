# NMVS Backend (reviewed build)

## Included corrections

- Removed the real `.env` file from the deliverable; configure your own local `.env` from `.env.example`.
- Removed wildcard CORS origins and the permissive origin regex. Set explicit frontend origins with `CORS_ALLOWED_ORIGINS`.
- Required authentication for `GET /auth/users`.
- Prevented password-reset OTPs from being written to logs or returned after SMTP delivery fails; failed delivery invalidates the stored OTP.
- Avoided returning raw database exception details to API clients.
- Removed hard-coded database and SMTP credential fallbacks; PostgreSQL now fails fast if required connection variables are missing.
- Removed the static development JWT secret fallback; development uses an ephemeral key when none is configured, and production requires a strong explicit key.
- Sanitized database diagnostics so passwords and raw exception details are not returned.
- Initialized database tables in the service tests so the suite runs consistently from a clean checkout.

## Setup

1. Install Python 3.11+ (Python 3.12 is a good default) and PostgreSQL only if you intend to use it.
2. Create an environment: `python -m venv .venv`
3. Activate it, then install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`. For local development, leave `DATABASE_URL` blank to use SQLite. For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL such as `postgresql+psycopg2://user:password@localhost:5432/nmvs` and URL-encode reserved characters in credentials. The legacy `DB_TYPE=postgres` and `POSTGRES_*` settings remain supported.
5. Generate a JWT secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and set `NMVS_SECRET_KEY` in `.env`. In production, set `NMVS_ENVIRONMENT=production` and use a unique random secret of at least 32 characters. The development fallback is ephemeral and invalidates tokens after restart.
6. Configure `SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally `SMTP_FROM_EMAIL` if password-reset emails are needed. For Gmail, use `smtp.gmail.com`, port `587`, the full Gmail address as `SMTP_USERNAME`, and a Google app password (not your normal account password) as `SMTP_PASSWORD`. If `SMTP_FROM_EMAIL` is unset, the authenticated username is used. If the API cannot deliver the email, `/auth/forgot-password` returns `503` instead of claiming it was sent; check the backend log for the SMTP failure, and check Spam/Junk in the recipient mailbox.
7. Individual device speed tests require a discovered agent-owned device inside a CIDR reported by the authenticated scanner agent, a recent Online report, and a device-mode agent heartbeat within 90 seconds. The scanner report persists its configured private IPv4 CIDR, including when the scan finds no devices. The target agent measures its own connection to Cloudflare and submits its measurements; the backend does not infer device speed from an IP address. Undiscovered, out-of-network, stale/offline, and agent-unavailable targets are rejected before a job is queued. Existing history rows that predate this workflow are marked `legacy_backend_label` and are not individual-device measurements. The agent's quick estimate uses one HTTP latency sample and caps each download/upload transfer at about three seconds. Each target device needs outbound HTTPS access to `speed.cloudflare.com`.
8. Monitoring checks registered devices at `DEVICE_MONITOR_INTERVAL` seconds (default `30`). Each cycle uses a start-to-start interval; if a scan runs longer than the interval, the next scan starts as soon as it finishes rather than overlapping it. Device checks run concurrently (up to 25 at a time) and each device result is logged in the backend terminal. Device checks use ICMP; optionally set a TCP service port per device for a fallback. A TCP latency value measures connection setup, not full application response time. Missing ICMP replies alone are shown as unknown rather than proof of outage. Explicit unreachable results raise a disconnect alert immediately; otherwise a disconnect alert is raised after `MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS` unverified checks (default `3`).
9. Optional monitoring thresholds can be set with `MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS` (default `3`), `MONITORING_HIGH_LATENCY_MS` (default `500`), and `MONITORING_UPTIME_THRESHOLD_PERCENT` (default `95`). Threshold alerts are deduplicated while active and a recovery alert is recorded when conditions clear.
10. HTTP health checks are disabled unless `MONITORING_HTTP_ALLOWED_HOSTS` is configured as a comma-separated exact-host allowlist. Only hosts explicitly present in that administrator-managed setting can be configured; hosts resolving to private, loopback, link-local, or other non-public IPs are rejected unless the literal IP itself is explicitly allowlisted. Redirects are not followed and URL credentials are rejected. Never put secrets in health-check URLs.
11. Monitoring API history is available at `/monitoring/history`; check-based availability summaries are available at `/monitoring/availability?days=1`, `7`, or `30`. Uptime is successful checks divided by successful plus explicitly failed checks; unknown checks and unobserved time are excluded.
12. Start the API from this directory: `uvicorn main:app --reload`
13. Open `/docs` for the API documentation.

The in-process scheduler requires a continuously running backend. Deploy it as a persistent service with one application worker; multiple workers each start their own scheduler, while serverless platforms such as Vercel cannot reliably run this loop. The Dashboard, Devices, Monitoring, and Alerts pages refresh their data every 30 seconds while open, and new-alert popups poll every 10 seconds. The application shows active device-status alerts when opened as well as newly created ones, so an active alert is not missed if it was created before the page loaded.

## Discovery ping

The authenticated `GET /discovery/ping/{ip}` endpoint checks ICMP reachability. If the device blocks ping, provide one known TCP service port as `?port=443`; a successful connection reports the device as online. A refused TCP connection also confirms that something at the address responded, though the service is not accepting connections. If neither check gets a response, the result is `Unknown`, not `Offline`, because a missing reply alone cannot establish that a device is offline.

## Local network agent

For discovery from a private LAN when the backend is hosted elsewhere, run the
agent on an authorized machine connected to that LAN. Configure
`NMVS_AGENT_TOKEN` on the backend and in `agent/.env` with the same strong,
private value; configure `NMVS_AGENT_API_URL` and `NMVS_AGENT_NETWORK` in
`agent/.env`. Use HTTPS for a remotely hosted backend. `POST /agent/scan-results`
requires a Bearer token, validates each result, creates or updates the device
entry, and writes the agent-reported status and latency to monitoring history
without re-probing the address from the backend. The token is for the local
agent only; never put it in the frontend.

## Verification

- Syntax check: `python -m compileall -q app database main.py tests`
- Backend tests (run from `backend`): `python -m unittest discover -s tests -v`
- Agent tests (run from the repository root): `python -m unittest discover -s agent\tests -v`
- Frontend production build: from `nmvs_frontend`, run `npm run build`.

The agent integration is covered by isolated SQLite API tests and mocked submission tests; scanning itself should only be run against an authorized network. Automated tests are not a substitute for testing against your actual network, administrator allowlist, and production database.

## Security before deployment

**The original uploaded ZIP contained real SMTP and database credentials. Rotate those credentials immediately**, especially the SMTP app password, and do not reuse the old values. Keep `.env` out of source control and shared ZIPs. Replace the development JWT secret with a long, random, unique value before deployment.
