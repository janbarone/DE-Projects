@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DOTA Pipeline Control Panel

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\dota_cli.py"
) else (
    py -3 "scripts\dota_cli.py"
)

if errorlevel 1 pause
endlocal
