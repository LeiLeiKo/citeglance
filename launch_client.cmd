@echo off
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    python -X utf8 "%~dp0desktop.py"
    if errorlevel 1 pause
) else (
    start "" pythonw.exe -X utf8 "%~dp0desktop.py"
)
