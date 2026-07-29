# Dashboard API Load Tests

The k6 suite exercises the dashboard's read-only API flow:

```text
GET /api/clients
GET /api/clients/:client_id/platforms
GET /api/clients/:client_id/platforms/:platform/overview
```

It intentionally excludes CSV upload, KPI writes, report-month deletion, Gemini,
and Google Slides generation. Those operations mutate data, consume external API
quota, or incur LLM cost and should use separate staging tests.

## Prerequisites

1. Start the dashboard and PostgreSQL:

   ```powershell
   docker compose up -d dashboard
   ```
2. Confirm that `http://127.0.0.1:8000/api/clients` returns at least one client
   with a connected platform.
3. Install k6, or run it from the official Docker image.

## Test Profiles

| Profile    | Default workload                    | Purpose                          |
| ---------- | ----------------------------------- | -------------------------------- |
| `smoke`  | 1 VU for 30 seconds                 | Verify the script and API        |
| `load`   | Ramp to 20 VUs for about 5 minutes  | Expected traffic                 |
| `stress` | Ramp to 100 VUs for about 8 minutes | Find degradation limits          |
| `spike`  | Jump from 5 to 100 VUs              | Sudden traffic increase          |
| `soak`   | 10 VUs for about 34 minutes         | Detect resource/connection leaks |

## Run Locally

Run the smoke profile first:

```powershell
k6 run `
  -e BASE_URL=http://127.0.0.1:8000 `
  -e TEST_TYPE=smoke `
  .\tests\load\dashboard_api.js
```

Run a normal load test against a specific client and month:

```powershell
k6 run `
  -e BASE_URL=http://127.0.0.1:8000 `
  -e TEST_TYPE=load `
  -e CLIENT_CODE=par `
  -e MONTH_SLUG=july-2026 `
  .\tests\load\dashboard_api.js
```

Run one platform only:

```powershell
k6 run `
  -e TEST_TYPE=stress `
  -e CLIENT_CODE=par `
  -e PLATFORM=instagram `
  .\tests\load\dashboard_api.js
```

Export the complete result as JSON:

```powershell
New-Item -ItemType Directory -Force .\test-results\k6 | Out-Null
k6 run `
  --summary-export .\test-results\k6\smoke-summary.json `
  -e TEST_TYPE=smoke `
  .\tests\load\dashboard_api.js
```

## Run with Docker

On Docker Desktop for Windows:

```powershell
docker run --rm `
  -v "${PWD}/tests/load:/scripts:ro" `
  grafana/k6 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e TEST_TYPE=smoke `
  /scripts/dashboard_api.js
```

## Configuration

| Environment variable | Default                   | Description                                             |
| -------------------- | ------------------------- | ------------------------------------------------------- |
| `BASE_URL`         | `http://127.0.0.1:8000` | Dashboard backend URL                                   |
| `TEST_TYPE`        | `smoke`                 | `smoke`, `load`, `stress`, `spike`, or `soak` |
| `CLIENT_ID`        | automatic                 | Exact client UUID                                       |
| `CLIENT_CODE`      | automatic                 | Client code such as`par`                              |
| `PERIOD_ID`        | latest                    | Exact report-period UUID                                |
| `MONTH_SLUG`       | latest                    | Month slug such as`july-2026`                         |
| `PLATFORM`         | all connected             | One platform or comma-separated platforms               |
| `AUTH_TOKEN`       | empty                     | Future bearer token support                             |
| `REQUEST_TIMEOUT`  | `15s`                   | Per-request timeout                                     |
| `THINK_TIME_MIN`   | `0.5`                   | Minimum pause between flows in seconds                  |
| `THINK_TIME_MAX`   | `1.5`                   | Maximum pause between flows in seconds                  |

## Pass/Fail Thresholds

The current baseline is:

```text
checks                         > 99%
HTTP request failure rate      < 1%
response validation failures   < 1%
GET clients p95                < 500 ms
GET platforms p95              < 750 ms
GET overview p95               < 1500 ms
```

These are initial engineering thresholds. Record the first stable staging run,
then adjust them to match the expected number of users and deployment resources.

During stress, spike, and soak tests, monitor in another terminal:

```powershell
docker stats mai_dashboard mai_postgres
docker logs mai_dashboard --tail 100
```

Do not run stress tests against production or trigger `/api/reports/slides`
without a dedicated test project, quota budget, and explicit approval.
