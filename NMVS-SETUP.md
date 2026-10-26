# NMVS setup and verification

## Components

- `nmvs_frontend` is the React/Vite client. It uses the existing user-authenticated API client and must never receive the agent credential.
- `backend` is the FastAPI API and persistent database service.
- `agent` runs on a machine with authorized access to the private network. It submits scan results over HTTPS to the API.
- SQLite is configured by default for local development. The backend resolves it to `backend/nmvs.db`.

## Configure secrets

Generate a random agent token locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the same new value in `backend/.env` as `NMVS_AGENT_TOKEN` and in
`agent/.env` as `NMVS_AGENT_TOKEN`. Copy the safe placeholders from
`backend/.env.example` and `agent/.env.example`; do not commit `.env` files or
put the agent token in any `VITE_*` variable. If a token was exposed, rotate it
on both sides and restart the backend and agent. The repository `.gitignore`
excludes `.env` files.

## Start locally (PowerShell)

Backend terminal:

```powershell
Set-Location "C:\Users\harir\Downloads\NMVS-Project-main\backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Frontend terminal:

```powershell
Set-Location "C:\Users\harir\Downloads\NMVS-Project-main\nmvs_frontend"
npm install
npm run dev
```

Agent terminal:

```powershell
Set-Location "C:\Users\harir\Downloads\NMVS-Project-main\agent"
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with the shared token and an authorized private CIDR.
python agent.py
```

The agent scans the configured private network (default
`192.168.43.0/24`) every 30 seconds. Set `NMVS_AGENT_API_URL` to the API origin
(default local example `http://127.0.0.1:8000`), and optionally set
`NMVS_AGENT_SCAN_INTERVAL_SECONDS` to 1–86400. For a remote API, HTTPS is
required.

### True per-device speed tests

The network-scanner agent can report reachability but cannot measure another
device's bandwidth. To measure an individual device, install Python and the
agent dependencies on that target device, configure its private `agent/.env`
with the backend URL and shared agent token, and set:

```dotenv
NMVS_AGENT_MODE=device
NMVS_AGENT_SPEED_TEST_POLL_SECONDS=5
```

Start `python agent.py` on each target device. Keep the scanner agent running
on the LAN to refresh Online status and report its configured CIDR to NMVS.
The Speed page accepts only a discovered IP inside a configured scanner CIDR,
with an Online report no older than two minutes and a device-mode agent that
has polled NMVS within the last 90 seconds. An undiscovered, out-of-network,
offline, stale, or agent-unavailable target is rejected before a speed-test
job is queued. The device agent performs the measurement; the backend never
substitutes its own speed.

Older speed-history rows are labeled `legacy_backend_label`: their IP was a
label only and does not identify the device whose bandwidth was measured.

## Agent and monitoring behavior

The local agent reports hosts that respond to ICMP. A ping timeout is not proof
that a device is offline, so hosts that do not reply are omitted from a scan;
the agent does not fabricate an Offline result or latency. A measured latency
is stored only when the platform's ping output reports an exact RTT. The API
accepts `Online`, `Offline`, or `Unknown` records from trusted agents, validates
IP and latency, and persists each accepted sample. Agent-owned devices are not
probed by the cloud backend's local-network monitoring scheduler. To refresh
their status, keep the agent running on the LAN.

## Verify the stored data (read-only)

The backend database tables are `devices` and `monitoring_history`. Run this
read-only query using Python from the `backend` directory:

```powershell
python -c "import sqlite3; db=sqlite3.connect('file:nmvs.db?mode=ro', uri=True); print(db.execute(\"SELECT d.ip, d.source, m.status, m.latency_ms, m.checked_at FROM devices d JOIN monitoring_history m ON m.ip=d.ip WHERE d.source='agent' ORDER BY m.checked_at DESC, m.id DESC LIMIT 20\").fetchall()); db.close()"
```

Never use a writable connection or clear history to validate a deployment.

## Tests

From the repository root:

```powershell
Set-Location "C:\Users\harir\Downloads\NMVS-Project-main\backend"
python -m unittest discover -s tests -v

Set-Location "C:\Users\harir\Downloads\NMVS-Project-main"
python -m unittest discover -s agent\tests -v

Set-Location "C:\Users\harir\Downloads\NMVS-Project-main\nmvs_frontend"
npm run build
```

Backend tests use an isolated in-memory SQLite database. Agent network requests
are mocked. These checks do not substitute for a real, authorized LAN scan or a
deployed HTTPS backend test.
