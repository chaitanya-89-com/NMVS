# NMVS local agent

The agent scans a private network from a machine connected to that network and
submits discovered devices to the NMVS backend.

## Configure

1. Install Python and the agent dependencies:

   ```powershell
   cd agent
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set the backend URL, a strong agent token,
   and the private network CIDR to scan:

   ```dotenv
   NMVS_AGENT_API_URL=http://127.0.0.1:8000
   NMVS_AGENT_TOKEN=your-shared-random-agent-token
   NMVS_AGENT_NETWORK=192.168.1.0/24
   NMVS_AGENT_SCAN_INTERVAL_SECONDS=30
   ```

3. Set the same `NMVS_AGENT_TOKEN` on the backend and restart the backend.
   Keep both environment files private; `.env` files are ignored by Git.
4. Run the agent:

   ```powershell
   python agent.py
   ```

`NMVS_AGENT_API_URL` is the backend origin, not the `/agent/scan-results`
endpoint. HTTPS is required except when testing against `localhost`.
`NMVS_AGENT_NETWORK` is optional and defaults to `192.168.43.0/24`.
The agent sends an empty result list when no devices respond. It scans and
submits continuously every 30 seconds by default; set
`NMVS_AGENT_SCAN_INTERVAL_SECONDS` to a value from 1 to 86400 to change this.
Each authenticated scan submission also reports its configured private IPv4
CIDR so the backend can enforce speed-test network membership.
Agent-owned devices are excluded from the backend's cloud-side scheduled
probes, so keep the scanner agent running to refresh their reachability.
Connection timeouts and server errors are retried up to three times with
backoff. Authentication and validation errors stop the agent instead of
retrying the same rejected request indefinitely; press Ctrl+C to stop a
healthy polling agent.

## Individual device speed tests

A speed test for a device is executed by an NMVS agent running on that device;
the backend cannot measure another host's internet bandwidth from its IP
address. Install Python and the agent dependencies on every device you want
to test, configure that device's local `agent/.env` with the backend origin
and the same private agent token, then use:

```dotenv
NMVS_AGENT_MODE=device
NMVS_AGENT_SPEED_TEST_POLL_SECONDS=5
```

Start `python agent.py` on the target. It identifies its own local IP, polls
for jobs, and measures that machine's connection to Cloudflare. Its polling
requests act as a short-lived availability heartbeat; run it against the same
backend as the scanner and Speed Monitoring page. The scanner
agent alone cannot measure other devices' bandwidth; each target must run its
own device agent. The UI accepts only a registered agent-discovered device
inside a recently reported scanner CIDR, whose latest agent report says
Online within the last two minutes, and whose device agent has polled within
the last 90 seconds. If these conditions are not met, the API rejects the
request instead of reporting a backend measurement.

## Troubleshooting

- **401 Unauthorized:** set the same `NMVS_AGENT_TOKEN` on the backend and in
  this agent's `.env`, then restart the backend.
- **422 Unprocessable Entity:** confirm the scan payload has valid IP addresses
  and only supported status values; each request is limited to 4096 devices.
- **Connection or timeout error:** check that the backend is running and that
  `NMVS_AGENT_API_URL` is its API origin. Use HTTPS for a hosted backend.

To test the endpoint in Swagger, open `/docs`, select **Authorize**, enter the
agent token (without the `Bearer ` prefix), then execute
`POST /agent/scan-results`.
