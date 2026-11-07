@echo off
setlocal
where py >nul 2>&1
if errorlevel 1 (
    echo Install Python 3.12 with its Windows launcher, then run setup.bat.
    exit /b 1
)
py -3.12 "%~dp0scripts\bootstrap.py" %*
exit /b %errorlevel%
