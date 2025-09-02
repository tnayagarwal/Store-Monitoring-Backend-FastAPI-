# Store Monitoring Backend (FastAPI)

FastAPI backend that computes uptime/downtime metrics for stores using status observations, business hours, and timezones.

## Features

- Trigger background report generation and poll for completion
- Loads CSV data on-demand from `data/`
- Outputs a CSV per report under `reports/`

## Project structure

```
app/
  main.py          # FastAPI app and endpoints
  db.py            # SQLAlchemy engine and session
  models.py        # ORM models
  loader.py        # CSV loader (accepts alt names: menu_hours.csv, timezones.csv)
  report.py        # Metrics computation and CSV writer
  time_utils.py    # Time interval helpers
data/
  store_status.csv
  business_hours.csv | menu_hours.csv
  store_timezone.csv | timezones.csv
reports/
requirements.txt
README.md
```

## Quickstart

1) Create venv and install deps (Windows PowerShell):

```
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2) Configure database (PostgreSQL):

Set environment variables as needed (defaults shown):

```
$env:PGUSER="postgres"
$env:PGPASSWORD="TaNaY"
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGDATABASE="assignment"
```

3) Prepare data files in `data/` (any of the accepted names):

- **Observations**: `store_status.csv`
- **Business hours**: `business_hours.csv` or `menu_hours.csv`
- **Timezones**: `store_timezone.csv` or `timezones.csv`

4) Run the API:

```
uvicorn app.main:app --reload
```

## API Endpoints

- `POST /trigger_report`
  - Returns: `{ "report_id": "<uuid>" }`
  - Starts background CSV generation. Data is auto-loaded on first run if CSVs exist.

- `POST /load_data`
  - Loads CSVs into the database (idempotent). Returns `{ "status": "ok" }`.

- `GET /get_report?report_id=<uuid>`
  - If still running: returns plain text status (e.g., `Running`).
  - When complete: streams the CSV. Response header `X-Report-Status: Complete` and `Content-Disposition` filename.

- `GET /debug_report?report_id=<uuid>`
  - Returns internal status JSON including `file_path` and any `error_message`.

## Output columns

- `store_id`
- `uptime_last_hour(in minutes)`
- `uptime_last_day(in hours)`
- `update_last_week(in hours)`
- `downtime_last_hour(in minutes)`
- `downtime_last_day(in hours)`
- `downtime_last_week(in hours)`

Note: "update_last_week(in hours)" is uptime for the last week (name kept for parity).

## Notes on logic

- "Now" is the maximum observation timestamp in the dataset (UTC naive).
- Business hours are interpreted in each store's local timezone, converted to UTC intervals. Missing hours imply 24x7.
- Missing timezone defaults to `America/Chicago`.
- Status interpolation is piecewise-constant between observations.

## Development

- Format: follow existing style; keep functions small and explicit.
- Consider adding tests for time overlaps and interpolation.
- Potential future work: async SQLAlchemy, streaming writers, pre-bucketing, retries.

## License

MIT

