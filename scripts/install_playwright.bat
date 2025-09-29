@echo off
REM Installs Playwright browsers into the virtualenv
poetry run python -m playwright install --with-deps chromium