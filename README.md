# Funds Agentic (LangGraph + Playwright)

## 1) Create environment
```bash
# Requires Poetry installed
poetry env use 3.12
poetry install
# Install Playwright browsers (once)
poetry run scripts/install_playwright.bat
```

## 2) Configure (optional)
Copy `.env.example` → `.env` and fill Google credentials if you plan to read Google Sheets.

## 3) Run
```bash
# Excel input
poetry run funds-agentic \
  --output "G:/My Drive/Investments/scraper" \
  --input "G:/My Drive/Investments/Holdings/AllHoldings_Updated.xlsx"

# Google Sheet (share with your service account email)
poetry run funds-agentic \
  --output "G:/My Drive/Investments/scraper" \
  --gsheet-url "https://docs.google.com/spreadsheets/d/..." \
  --sheet "TrackingList"
```

### CLI flags (most common)
- `--input <path.xlsx>` **or** `--gsheet-url <url>` **or** `--gdrive-id <id>`
- `--output <dir>` (required)
- `--sheet <name>` (default `TrackingList`)
- `--row-start <int>` (default `3`)
- `--col-url/--col-hold/--col-holding` (header overrides)
- `--headless true|false` (default true)
- `--retries-per-url <int>` (default 2)
- `--nav-timeout <sec>` (default 20)

### Outputs
Creates date-stamped pairs in the output directory:
- `YYYY-MM-DD_funds.csv` and `.parquet`
- `YYYY-MM-DD_sectors.csv` and `.parquet`
