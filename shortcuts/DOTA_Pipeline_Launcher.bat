@echo off
setlocal EnableExtensions
title DOTA Pipeline Launcher

REM ============================================================
REM  DOTA 2 Pipeline - Launcher
REM  Double-click this file (or run it from a terminal).
REM  Project root is one level up from this shortcuts folder.
REM ============================================================

for %%i in ("%~dp0..") do set "ROOT=%%~fi"
cd /d "%ROOT%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
set "DBT=%ROOT%\.venv\Scripts\dbt.exe"

if not exist "%PY%" (
    echo [ERROR] Python virtualenv not found at:
    echo          "%PY%"
    echo.
    echo Run these once to set it up:
    echo    python -m venv .venv
    echo    .venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
    echo.
    pause
    exit /b 1
)

:menu
cls
echo ================================================================
echo    DOTA 2 Pipeline - Launcher
echo ================================================================
echo    Project: %ROOT%
echo ----------------------------------------------------------------
echo.
echo    [1] Incremental update   - load new scrape + dbt build
echo    [2] Full rebuild+refresh - dbt build --full-refresh
echo    [3] Scrape new matches   - interactive fetcher (saves to data/)
echo    [4] Refresh constants    - heroes / items / abilities / modes
echo    [5] Full pipeline        - constants + load + build + backup
echo    [6] dbt tests only
echo    [7] Backup database      - pg_dump snapshot (backups/)
echo    [8] Start Postgres       - docker compose up -d
echo    [9] Open Power BI report
echo.
echo    [0] Exit
echo.
echo    NOTE: options 1,2,5,6,7 require Postgres (Docker) running.
echo ================================================================
set /p "CHOICE=Select an option: "

if "%CHOICE%"=="1" goto incr
if "%CHOICE%"=="2" goto fullrefresh
if "%CHOICE%"=="3" goto scrape
if "%CHOICE%"=="4" goto constants
if "%CHOICE%"=="5" goto fullpipeline
if "%CHOICE%"=="6" goto tests
if "%CHOICE%"=="7" goto backup
if "%CHOICE%"=="8" goto docker
if "%CHOICE%"=="9" goto powerbi
if "%CHOICE%"=="0" exit /b 0
echo.
echo    Invalid choice. Press a key to try again.
pause
goto menu

REM ============================================================
REM  Option 1 - Incremental update
REM ============================================================
:incr
call :need_db
echo.
echo [1] Incremental update: loading new scrape into bronze, then dbt build...
echo.
"%PY%" "scripts\load_bronze.py" --data-dir data
if errorlevel 1 goto failed
"%DBT%" build --profiles-dir . --project-dir transform --threads 1
if errorlevel 1 goto failed
echo.
echo Done. Incremental update complete.
pause
goto menu

REM ============================================================
REM  Option 2 - Full rebuild + refresh
REM ============================================================
:fullrefresh
call :need_db
echo.
echo [2] Full dbt rebuild + refresh (--full-refresh). This takes ~45-60 min.
echo.
"%DBT%" build --profiles-dir . --project-dir transform --threads 1 --full-refresh
if errorlevel 1 goto failed
echo.
echo Done. Full rebuild complete.
pause
goto menu

REM ============================================================
REM  Option 3 - Scrape new matches
REM ============================================================
:scrape
echo.
echo [3] Scraping new matches (interactive). Press Ctrl+C to stop at any time.
echo     NOTE: this only downloads raw JSON to data/. Run option [1] next
echo     to load it into the database.
echo.
"%PY%" "data\_fetch_matches.py"
pause
goto menu

REM ============================================================
REM  Option 4 - Refresh constants
REM ============================================================
:constants
echo.
echo [4] Refreshing static constants (heroes/items/abilities/...)...
echo.
"%PY%" "data\_fetch_constants.py" --data-dir data
echo.
echo Done.
pause
goto menu

REM ============================================================
REM  Option 5 - Full pipeline
REM ============================================================
:fullpipeline
call :need_db
echo.
echo [5] Full pipeline: constants + load bronze + dbt build + backup...
echo.
"%PY%" "scripts\run_pipeline.py" --data-dir data --refresh-constants --backup
if errorlevel 1 goto failed
echo.
echo Done. Full pipeline complete.
pause
goto menu

REM ============================================================
REM  Option 6 - dbt tests only
REM ============================================================
:tests
call :need_db
echo.
echo [6] Running dbt tests...
echo.
"%DBT%" test --profiles-dir . --project-dir transform --threads 1
if errorlevel 1 goto failed
echo.
echo Done.
pause
goto menu

REM ============================================================
REM  Option 7 - Backup database
REM ============================================================
:backup
call :need_db
echo.
echo [7] Backing up the database (pg_dump -> backups/)...
echo.
"%PY%" "scripts\run_pipeline.py" --only-backup --backup-docker
if errorlevel 1 goto failed
echo.
echo Done.
pause
goto menu

REM ============================================================
REM  Option 8 - Start Postgres
REM ============================================================
:docker
echo.
echo [8] Starting Postgres via docker compose...
echo.
docker compose up -d
echo.
docker ps
echo.
echo If you do not see 'dota_postgres' running, make sure Docker Desktop is started.
pause
goto menu

REM ============================================================
REM  Option 9 - Open Power BI report
REM ============================================================
:powerbi
echo.
echo [9] Opening the Power BI report...
echo     NOTE: keep Power BI Desktop closed while editing .pbip files by hand.
echo.
start "" "%ROOT%\.pbip\dota pipeline.pbip"
pause
goto menu

REM ============================================================
REM  Helpers
REM ============================================================
:need_db
docker ps --format "{{.Names}}" 2>nul | findstr /c:"dota_postgres" >nul
if not errorlevel 1 goto :eof
echo.
echo [WARN] Postgres container 'dota_postgres' is not running.
set /p "ANS=Start it now with docker compose up -d? [y/n]: "
if /i "%ANS%"=="y" docker compose up -d
goto :eof

:failed
echo.
echo [ERROR] The last command failed.
echo         Make sure Docker Desktop is running and Postgres is up (option 8).
echo.
pause
goto menu
