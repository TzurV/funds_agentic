# Funds Agentic - local Windows CLI

Collect Trustnet fund and IA sector performance into validated CSV snapshots. The application uses ordinary typed Python functions, Pydantic, pandas, and Playwright. It does not require LangGraph or create Parquet files.

## Set up this computer

Install Python **3.12** with the Windows Python launcher. Check it with `py -3.12 --version`.

Open a terminal in the Google Drive project folder and run:

```bat
setup.bat
run.bat --check
```

Setup creates an isolated Poetry tooling environment, a separate application virtual environment, and the matching Chromium installation under `runtime/<computer-id>/`. Poetry 2.2.1 synchronizes application dependencies from `poetry.lock`; ordinary runs do not install or upgrade dependencies. Existing `.venv` and historical exports are left intact.

Run `setup.bat` again explicitly after the dependency lock, Python installation, or project location changes. Python itself must be installed locally. A virtual environment copied from another computer is not portable.

## Configure shared inputs and outputs

Edit `configuration/settings.toml`. Its `shared_root` is relative to that file. The default layout expects:

```text
Investments/
    Github/funds-agentic/configuration/settings.toml
    Holdings/AllHoldings_Updated.xlsx
    scraper/
```

Input and output paths, including relative CLI overrides, resolve against `shared_root`. Absolute paths are accepted. No drive letter or Windows username is hardcoded.

Optional per-computer overrides belong in `configuration/machines/<computer-id>.local.toml`, which is excluded from Git. They can override `shared_root` and `[scraper]` settings. The computer ID defaults to the lowercase Windows hostname. Set `FUNDS_COMPUTER_ID` consistently before both setup and running if a different ID is needed.

The default Excel reader uses headers on row 3. Named URL, Hold, and Holding% columns are preferred. The existing F/G/H layout remains supported with an explicit warning; disable that fallback using `--no-legacy-columns`. Invalid overrides, conflicting duplicate funds, and unusable input fail clearly. Workbooks are read without being modified.

## Run

```bat
run.bat
run.bat --check
run.bat --output "Github/funds-agentic/workspace/verification"
run.bat --limit 5 --output "Github/funds-agentic/workspace/sample"
run.bat --no-headless
```

`--check` validates configuration and reads inputs without opening a browser or writing exports. `--limit` is always a verification run: it saves its own snapshot but never replaces compatibility exports or `latest.json`.

The launcher works from a different current directory as well:

```bat
"G:\My Drive\Investments\Github\funds-agentic\run.bat" --check
```

The example path can differ on each computer.

Supported overrides include `--config`, `--input`, `--gsheet-url`, `--gdrive-id`, `--output`, `--sheet`, `--row-start`, `--col-url`, `--col-hold`, `--col-holding`, `--retries-per-url`, `--nav-timeout`, `--headless`, and `--no-headless`. Retry count means total attempts. Obsolete LangGraph visualization flags have been removed.

### Google Sheets

Share the spreadsheet with a service account and set either `GOOGLE_APPLICATION_CREDENTIALS` to its credential-file path or `GOOGLE_SERVICE_ACCOUNT_JSON` to its JSON credentials. Keep credentials out of Git. Select the source with `--gsheet-url` or `--gdrive-id`; this replaces the configured Excel source. Google Sheets header row offsets match the Excel behavior.

### Results and failure behavior

A complete validated run publishes:

- `YYYYMMDD_funds.csv` and `YYYYMMDD_sectors.csv`, preserving legacy columns, column order, CSV index, and two-decimal numeric formatting.
- A unique directory under `runs/<run-id>/` containing both CSVs and `run.json` diagnostic metadata.
- `latest.json`, identifying the coherent successful snapshot. Resolve its CSV filenames relative to its `snapshot` directory.

Partial and failed collections are marked explicitly and do not replace the last successful compatibility exports or latest pointer. Source-provided missing returns retain their correct periods. Price dates are recorded separately from performance source dates; unavailable performance dates stay unknown.

The `price` column uses an explicitly labeled mid quote where available, otherwise bid and then offer, selected from the exact share-class row. Factsheet links and the Citicode identifier distinguish classes with identical names. Unit grids and merged bid/offer cells are supported even when they are inside hidden tabs. Price units and dates are retained in diagnostic metadata.

The legacy `Quartile` column retains the first, 3-month quartile. The source includes separate rankings for other periods; they are not added to the CSV schema in this phase.

CSV publication stages a run, keeps previous compatibility exports for recovery, and replaces each file individually. Two separate legacy files are not an atomic transaction: `latest.json` and its immutable snapshot identify the complete dataset. Failed alias publication attempts are rolled back where the filesystem allows recovery. Old run directories are not deleted automatically.

Exit codes: **0** successful complete run or input check; **2** partial/verification run; **1** failure. Warnings explain optional unavailable source fields. Missing required fund/IA sector coverage prevents successful publication. Funds in other universes retain their fund data, with an explicit warning that an IA-only sector export cannot support their sector comparison. IA Unclassified and IA Not Yet Assigned are explicitly reported as having no published benchmark; no sector values are invented for them.

Collection is sequential. Trustnet component or navigation failures are retried with bounded backoff; structural parsing errors are reported rather than guessed. Run duration depends on the number of funds and source responsiveness.

An output lock prevents concurrent writers using the same visible output folder. If a process is forcibly terminated, inspect `.funds-agentic.lock` before manually removing it. Google Drive synchronization does not provide reliable locking across computers: run on one computer at a time and allow synchronization to finish before switching.

## Tests

```bat
run.bat --test -q
```

Regression checks cover missing return cells, table formatting, input offsets, URL validation, pagination, source totals, resource cleanup, CSV schema, and interrupted publication. They use local fixtures or mocks and do not scrape the live website.

## Another Windows computer

1. Sync the project, configuration, and required input workbook to Google Drive; make required files available offline.
2. Install Python 3.12 with its launcher.
3. Run `setup.bat` there to build that computer's own environment and browser installation.
4. Run `run.bat --check` and a verification run in a separate output directory.
5. Check the results before using normal output paths.

Runtime directories are stored in Drive but excluded from Git. Each computer uses only its own runtime. Other-computer portability must be verified on that computer; local tests alone do not establish it.

See [the approved modernization plan](LOCAL_CLI_MODERNIZATION_PLAN.md) for scope and future options. Cloud hosting and ChatGPT tools remain future work.
