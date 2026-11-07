# Local CLI Modernization Plan

Date: 2026-11-07

Status: Approved for implementation by the user on 2026-11-07. Implement the local CLI phase on the working branch; future suggestions remain outside scope.

Baseline commit: `468526b` — Fix sector pagination and validation; clean up browser resources.

Baseline tag: `local-cli-baseline-2026-11-07`

Working branch: `refactor/local-cli-v2`

## 1. Objective

Harden the existing local Trustnet scraper so it produces dependable CSV data and can run from a shared Google Drive project on multiple Windows computers.

The first implementation and verification will take place on the current computer. Setup on other computers will follow after this version works here.

## 2. Decisions already made

- All target computers run Windows.
- Python will be installed locally once on each computer. Reuse a suitable existing installation where possible.
- Source code, configuration, inputs, outputs, and machine-specific virtual environments will reside in Google Drive.
- Each computer will have its own virtual environment; one environment will not be reused across computers.
- Keep Python, Pydantic, pandas where useful, pytest, and Playwright.
- Remove LangGraph and replace the linear graph with ordinary typed functions.
- Produce CSV data exports only. Remove Parquet generation and the `pyarrow` dependency.
- Leave existing Parquet files untouched.
- Do not implement a ChatGPT integration or cloud service in this phase.
- The user has agreed to begin implementation of this local CLI plan.

## 3. Proposed defaults for agreement

- Keep Poetry and the current locked dependency versions initially, apart from removing unused dependencies associated with LangGraph and Parquet.
- Preserve the current Excel workbook and Google Drive output locations through configuration; do not relocate user data as part of the refactor.
- Keep Excel and Google Sheets input support.
- Preserve the existing CSV filenames, column names, column order, timestamp presentation, and numeric formatting for existing consumers, unless a specific incompatibility is agreed before implementation.
- Keep the existing environment available until the replacement is verified.
- Retain partial results for diagnosis, but do not present them as the latest successful complete export.
- Make package upgrades and alternative environment tooling separate follow-up work.

## 4. Google Drive and Windows environment

### 4.1 Proposed project layout

```text
funds-agentic/
    src/
    tests/
    configuration/
    runtime/
        <computer-id>/
            .venv/
            browsers/
    run.bat
    pyproject.toml
    poetry.lock
    LOCAL_CLI_MODERNIZATION_PLAN.md
```

The existing holdings workbook and output folder may remain elsewhere under the shared Investments folder. They do not need to move into this repository.

`runtime/` will be excluded from Git. It may sync through Google Drive, but each computer will use only its own runtime directory. A synced virtual environment is not treated as portable.

Use a stable computer identifier to select the runtime. Provide an override if two computers have conflicting identifiers or a machine is renamed.

### 4.2 Launcher behavior

The Windows launcher will:

1. Find the project relative to the launcher location, independently of the current working directory.
2. Resolve configured paths without assuming a drive letter or username.
3. Identify the current computer and select its environment.
4. Check the local Python version and report a clear setup instruction if it is missing or incompatible.
5. Create or synchronize that computer's environment from the lock file during explicit setup, rather than unexpectedly upgrading packages on ordinary runs.
6. Check that the matching Playwright browser installation is available in that computer's runtime directory.
7. Invoke the application without requiring manual virtual environment activation.
8. Return a useful exit code and support unattended use without an unconditional pause.

Shared configuration will contain portable settings. Any machine-specific overrides will be separate and clearly documented. Paths will resolve against a defined configuration or shared-root location, not the shell's current directory.

Do not assume Google Drive synchronization provides cross-computer locking. Initial operation will be one active run at a time, with unique run identifiers to prevent accidental filename collisions.

## 5. Simplify the application structure

Replace the LangGraph pipeline with a small application service that calls typed functions for:

1. Loading and validating configuration.
2. Loading the fund list from Excel or Google Sheets.
3. Collecting sector and fund source data.
4. Parsing source data into typed records.
5. Validating records and overall coverage.
6. Publishing CSV exports and reporting the run outcome.

The command-line layer will parse arguments and call this service. Core functions will accept explicit inputs instead of reading or modifying `sys.argv`.

Use Pydantic for configuration and record validation where useful. Browser contexts, pages, and Playwright handles will remain execution resources; they will not be stored in shared data models or serialized as application state.

Return a structured run result containing status, counts, errors, and output paths. Include enough detail to distinguish successful, partial, and failed runs.

## 6. Correct and harden extraction

### 6.1 Fund performance

- Replace whitespace-token parsing with extraction based on explicit headers and row labels.
- Preserve missing values in their original periods.
- Support source tables whose headers or values are separated by line breaks.
- Distinguish a legitimately unavailable return from an extraction failure.
- Validate required identity and performance structure before counting a fund as successfully scraped.

### 6.2 Fund identity, sector, quartile, risk, and price

- Locate values through the relevant labels and table structure instead of their incidental position on the page.
- Extract the price from its identified field, not the first number-like token in a table.
- Validate quartiles against the expected domain when supplied.
- Normalize sector links and retain stable identifiers internally where available.
- Record missing or invalid fields explicitly instead of silently swallowing every error.
- Preserve CSV schema compatibility while improving internal records.

### 6.3 Sector performance

- Retain table-scoped pagination and waiting for actual row changes.
- Reject duplicate sectors, blank identities, and empty extraction.
- Verify completeness against the source's reported total when available.
- Check that sectors required by successfully identified tracked funds are covered, or explain why they are unavailable.
- Do not hardcode today's total of 55 sectors as a permanent rule.
- Validate performance values and distinguish source missing values from parsing failures.

### 6.4 Input handling

- Fix the Google Sheets double-slicing bug that skips the first fund when the header is on row 3.
- Validate required columns and explicit column overrides.
- Make Excel's legacy positional-column fallback explicit and visible in diagnostics.
- Validate fund URLs before opening them.
- Deduplicate consistently and identify conflicting duplicate input records.
- Report empty or unusable input clearly.

### 6.5 Browser lifecycle and retries

- Close every fund and sector page after use, including failure paths.
- Always close the browser context, browser, and Playwright process through unconditional cleanup.
- Wait for the required source elements instead of relying on arbitrary delays.
- Use one understandable retry policy with clear attempt counts and backoff.
- Retry transient navigation or loading failures; report deterministic validation failures clearly.
- Keep collection sequential initially. Introduce concurrency only if later measurements justify it.

## 7. Validation, timestamps, and CSV publication

- Remove Parquet writes, Parquet output paths, related reporting, and the direct `pyarrow` dependency.
- Keep CSV as the only market-data export format. Ordinary logs and completion metadata may support diagnosis and publication.
- Preserve compatibility exports named `YYYYMMDD_funds.csv` and `YYYYMMDD_sectors.csv`.
- Use unique run identifiers and retain run-specific CSVs so same-day reruns remain distinguishable.
- Stage and validate exports before publication; preserve the previous successful run when collection or writing fails.
- Use a completion marker or equivalent publication mechanism to identify a coherent completed run. Do not treat two independent file replacements or Drive synchronization as an atomic transaction.
- Do not log a partial or failed run as a successful complete refresh.
- Use timezone-aware timestamps for Europe/London. Keep retrieval time distinct from source data dates when the source provides them.
- Include run ID, duration, requested/successful/failed fund counts, sector coverage, and actionable errors in diagnostics.
- Report unavailable source dates honestly rather than substituting retrieval time as the source date.

## 8. Verification and acceptance criteria

### 8.1 Automated regression checks

Cover the meaningful failure cases:

- Missing performance values do not shift later periods.
- Header formatting changes do not silently erase all performance values.
- Excel and Google Sheets header offsets return the expected fund rows.
- Unrelated page controls do not affect sector pagination.
- Stalled, repeated, empty, and incomplete sector pages fail clearly.
- Legitimately unavailable values are distinguished from broken extraction.
- Browser resources are released on successful and failed runs.
- A publication failure preserves the previous successful run.
- No Parquet files are generated and no Parquet-specific dependency is required.
- Path resolution works independently of the working directory and configured Drive root.
- Existing CSV consumers receive the agreed compatible schema and formatting.

### 8.2 Live verification on this computer

1. Set up the new machine-specific runtime without removing the old environment.
2. Run against the current Excel input into a separate verification output location.
3. Compare selected fund and sector values with Trustnet, including the previously missing sectors.
4. Confirm counts, sector coverage, missing-data explanations, filenames, and output formatting.
5. Confirm useful behavior for failed navigation and incomplete extraction.
6. After validation and user acceptance, designate the new launcher as the normal local workflow.

### 8.3 Acceptance outcome

The phase is complete when the new CLI works on this computer, the relevant regression checks pass, CSV outputs are validated, LangGraph and Parquet generation are removed, and setup for another Windows computer is documented.

Cross-computer portability will be confirmed by an actual run on another computer when the user is ready. It will not be claimed as fully tested from the first computer alone.

## 9. Proposed implementation order after agreement

1. Establish regression coverage for the confirmed parsing and input bugs.
2. Introduce the portable configuration and machine-specific runtime setup here.
3. Replace LangGraph with typed functions and explicit resource ownership.
4. Correct fund extraction and strengthen sector completeness checks.
5. Implement CSV-only validated publication and clear run reporting.
6. Run the live comparison and compatibility checks in the verification output location.
7. Update operating and setup instructions.
8. Review the result with the user before setting up the other computers.

## 10. Boundaries for this phase

- No cloud deployment, remote MCP service, or ChatGPT plugin.
- No replacement investment-analysis or portfolio-advice logic.
- No new database and no reintroduction of Parquet.
- No automatic deletion of historical exports or the old environment.
- No wholesale dependency upgrade or package-manager migration.
- No replacement of Playwright until an alternative collection path has been demonstrated to work reliably.

## Appendix A. Future suggestions — not authorized implementation scope

### A1. Reduce dependence on browser interaction

Investigate Trustnet's own data-loading requests and any supported export or licensed data feed. The sector page currently contains a form targeting `/umbraco/surface/search/GetLeadingSectorsAZ`, with universe, performance column set, page, and page-size parameters.

A direct request during the review returned HTTP 500. A reliable browser-free replacement has not been established. Treat this internal endpoint as an investigation lead, not a supported public API.

If proven suitable, add an HTTPX-based collector and an HTML parser such as lxml behind the same typed collection interface, with Playwright retained where necessary. Verify permitted access and source stability before relying on an alternative.

### A2. Scheduled hosted collection

Package the working CLI as a container and run it on a schedule or on demand. A small VM or managed container job could hold the execution environment, while shared storage retains validated snapshots and CSV exports.

Test Trustnet access from the intended host early. Keep credentials outside the source repository. Hosting selection, costs, and operational requirements need a separate decision.

### A3. Remote tools callable from ChatGPT

Expose the hosted service through an authenticated remote MCP integration, subject to the user's account, workspace policies, and client support.

Possible tools:

- `refresh_data(portfolio_id, scope)` — start a refresh and return a persistent run ID.
- `get_run(run_id)` — inspect progress, validation, and failures.
- `get_snapshot(portfolio_id, snapshot_id)` — retrieve a validated dataset.
- `get_sector_performance(sector_id, snapshot_id)` — retrieve sector observations.
- `get_exports(snapshot_id)` — obtain CSV download links.

Store operational state on the service so work can be queried from another computer or conversation. Do not rely on a ChatGPT thread to own the worker process or its state. A remote tool does not automatically install or authenticate itself on every client.

The service could use the official Python MCP SDK. A separate FastAPI API is optional and would be justified by additional clients or a dashboard. A custom visual interface is not required for the initial tools.

### A4. Environment tooling and dependency maintenance

Consider uv after the refactor is stable. Compare its setup and lock-file workflow with the existing Poetry workflow before migrating. Upgrade dependencies separately with focused checks and a matching Playwright browser installation.

Add automated repository checks for regression tests, formatting, and dependency maintenance when useful.

### A5. Historical queries and analysis

If CSV history becomes awkward to query, assess a database in a separate phase. Keep market observations separate from portfolio holdings, preserve source identifiers and dates, and provide reproducible fund-versus-sector comparisons.

This suggestion does not authorize adding a database or restoring Parquet output.

## Appendix B. Reference documentation

- Python virtual environments and portability: https://docs.python.org/3/library/venv.html
- Playwright Python container support: https://playwright.dev/python/docs/docker
- HTTPX: https://www.python-httpx.org/
- lxml HTML parsing: https://lxml.de/lxmlhtml.html
- uv projects: https://docs.astral.sh/uv/guides/projects/
- OpenAI MCP server implementation: https://developers.openai.com/plugins/build/mcp-server
- Connecting remote tools to ChatGPT: https://developers.openai.com/plugins/deploy/connect-chatgpt
- ChatGPT MCP and client configuration guidance: https://learn.chatgpt.com/docs/extend/mcp
- Google Cloud Run Jobs: https://docs.cloud.google.com/run/docs/quickstarts/jobs/create-execute

Integration availability and provider documentation should be checked again when a future phase is approved.
