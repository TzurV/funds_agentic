@echo off
REM Batch script to run funds-agentic with proper PYTHONPATH using virtual environment

REM Activate virtual environment
call "%~dp0.venv\Scripts\activate.bat"

REM Set PYTHONPATH to src directory
set PYTHONPATH=%~dp0src

REM Run the application
python -m funds_agentic.main --output "G:/My Drive/Investments/scraper" --input "G:/My Drive/Investments/Holdings/AllHoldings_Updated.xlsx" --retries-per-url 3

REM Pause to see output (remove if running in automation)
pause
